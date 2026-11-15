"""Shared Scorecard state for BidWise tender evaluation system.

Maintains centralized state across all agents with thread/async lock protection.
"""

from __future__ import annotations

import asyncio
import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from logs.logger import log_event


@dataclass
class Scorecard:
    """Central shared scorecard read and updated by all agents."""

    tender_id: str
    run_id: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S"))
    criteria: Dict[str, Any] = field(default_factory=dict)
    # bids format: {bid_id: {vendor, scores, compliance, disqualified, disqualification_reason, total, rank, delivery_days, price, features}}
    bids: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    winner: Optional[str] = None
    justification: Optional[str] = None
    tie_break_applied: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    def init_bid(self, bid_id: str, vendor_name: str = "") -> None:
        """Initializes a bid entry if not present."""
        if bid_id not in self.bids:
            self.bids[bid_id] = {
                "bid_id": bid_id,
                "vendor_name": vendor_name or bid_id,
                "scores": {},
                "compliance": {"compliant": True, "reasons": []},
                "disqualified": False,
                "disqualification_reason": None,
                "total": 0.0,
                "rank": None,
                "delivery_days": None,
                "price": None,
                "features": {},
            }

    async def record_event(self, agent: str, action: str, detail: str) -> None:
        """Records an event in memory and to the append-only run log."""
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        evt = {"timestamp": ts, "agent": agent, "action": action, "detail": detail}
        async with self._lock:
            self.events.append(evt)
        log_event(
            run_id=self.run_id,
            agent=agent,
            tool="Scorecard.record_event",
            input_summary=f"action={action}",
            output_summary=detail,
        )

    async def update_criteria(self, criteria_dict: Dict[str, Any], agent: str = "CriteriaAgent") -> None:
        """Updates the evaluation criteria and weights."""
        async with self._lock:
            self.criteria = criteria_dict
        await self.record_event(agent, "update_criteria", f"Registered {len(criteria_dict)} criteria")

    async def update_compliance_slice(
        self,
        bid_id: str,
        is_compliant: bool,
        reasons: List[str],
        disqualified: bool = False,
        disqualification_reason: Optional[str] = None,
        agent: str = "ComplianceAgent",
    ) -> None:
        """Thread-safe update of the compliance slice for a bid."""
        async with self._lock:
            self.init_bid(bid_id)
            self.bids[bid_id]["compliance"] = {"compliant": is_compliant, "reasons": reasons}
            if disqualified:
                self.bids[bid_id]["disqualified"] = True
                self.bids[bid_id]["disqualification_reason"] = disqualification_reason or (
                    reasons[0] if reasons else "Compliance check failed"
                )
        status_text = "DISQUALIFIED" if disqualified else ("COMPLIANT" if is_compliant else "NON-COMPLIANT")
        await self.record_event(
            agent,
            "update_compliance_slice",
            f"Bid {bid_id} evaluated: {status_text} ({', '.join(reasons) if reasons else 'OK'})",
        )

    async def update_technical_slice(
        self,
        bid_id: str,
        tech_score: float,
        exp_score: float,
        features: Dict[str, Any],
        agent: str = "TechnicalScorer",
    ) -> None:
        """Thread-safe update of the technical & experience scoring slice."""
        async with self._lock:
            self.init_bid(bid_id)
            self.bids[bid_id]["scores"]["technical"] = tech_score
            self.bids[bid_id]["scores"]["experience"] = exp_score
            self.bids[bid_id]["features"].update(features)
        await self.record_event(
            agent,
            "update_technical_slice",
            f"Bid {bid_id}: Technical={tech_score:.2f}, Experience={exp_score:.2f}",
        )

    async def update_commercial_slice(
        self,
        bid_id: str,
        price: float,
        commercial_score: float,
        payment_terms_ok: bool,
        agent: str = "CommercialScorer",
    ) -> None:
        """Thread-safe update of the commercial scoring slice."""
        async with self._lock:
            self.init_bid(bid_id)
            self.bids[bid_id]["price"] = price
            self.bids[bid_id]["scores"]["commercial"] = commercial_score
            self.bids[bid_id]["features"]["payment_terms_ok"] = payment_terms_ok
        await self.record_event(
            agent,
            "update_commercial_slice",
            f"Bid {bid_id}: Price={price:.2f}, CommercialScore={commercial_score:.2f}",
        )

    async def update_delivery_slice(
        self,
        bid_id: str,
        delivery_days: int,
        delivery_score: float,
        agent: str = "TechnicalScorer",
    ) -> None:
        """Thread-safe update of the delivery timeline scoring slice."""
        async with self._lock:
            self.init_bid(bid_id)
            self.bids[bid_id]["delivery_days"] = delivery_days
            self.bids[bid_id]["scores"]["delivery"] = delivery_score
        await self.record_event(
            agent,
            "update_delivery_slice",
            f"Bid {bid_id}: DeliveryDays={delivery_days}, DeliveryScore={delivery_score:.2f}",
        )

    async def update_totals_and_ranks(
        self,
        ranked_bids: List[Dict[str, Any]],
        agent: str = "AwardManager",
    ) -> None:
        """Thread-safe update of bid total scores and rankings."""
        async with self._lock:
            for item in ranked_bids:
                bid_id = item["bid_id"]
                if bid_id in self.bids:
                    self.bids[bid_id]["total"] = item["total"]
                    self.bids[bid_id]["rank"] = item["rank"]
        summary = ", ".join(f"Rank {item['rank']}: {item['bid_id']} ({item['total']:.2f})" for item in ranked_bids)
        await self.record_event(agent, "update_totals_and_ranks", f"Rankings assigned: {summary}")

    async def set_tie_break_result(
        self,
        applied: bool,
        winner_id: str,
        detail: str,
        agent: str = "TieBreakAgent",
    ) -> None:
        """Thread-safe update when tie break criterion is applied."""
        async with self._lock:
            self.tie_break_applied = applied
        await self.record_event(
            agent,
            "tie_break_evaluation",
            f"Tie-break applied={applied}. Resolved winner={winner_id}. Detail: {detail}",
        )

    async def set_final_award(
        self,
        winner_id: str,
        justification: str,
        agent: str = "AwardManager",
    ) -> None:
        """Thread-safe update for the final award and justification."""
        async with self._lock:
            self.winner = winner_id
            self.justification = justification
        await self.record_event(agent, "final_award", f"Declared Winner: {winner_id}")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes scorecard state to standard dict."""
        return {
            "tender_id": self.tender_id,
            "run_id": self.run_id,
            "criteria": self.criteria,
            "bids": self.bids,
            "events": self.events,
            "winner": self.winner,
            "justification": self.justification,
            "tie_break_applied": self.tie_break_applied,
        }

    def save_json(self, output_path: Path) -> None:
        """Writes the serialized scorecard to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
