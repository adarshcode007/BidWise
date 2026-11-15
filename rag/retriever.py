"""In-memory Retriever for tender documents supporting TF-IDF and optional embeddings.

Exposes a unified Retriever interface in rag/retriever.py.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import GROQ_API_KEY, TENDER_PATH, has_groq_api_key


class Retriever:
    """Unified in-memory retriever for tender document clauses."""

    def __init__(self, corpus_path: Optional[Path] = None, use_embeddings: bool = False):
        self.corpus_path = Path(corpus_path) if corpus_path else TENDER_PATH
        self.use_embeddings = use_embeddings and has_groq_api_key()
        self.clauses: List[Dict[str, Any]] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self._load_and_index()

    def _split_into_clauses(self, text: str) -> List[Dict[str, Any]]:
        """Splits tender text into numbered clause chunks."""
        pattern = re.compile(r"(Clause\s+(\d+)\s*:[^\n]*\n)(.*?)(?=(Clause\s+\d+\s*:|\Z))", re.DOTALL | re.IGNORECASE)
        matches = list(pattern.finditer(text))
        clauses = []
        for m in matches:
            header = m.group(1).strip()
            clause_num = m.group(2).strip()
            body = m.group(3).strip()
            full_clause = f"{header}\n{body}".strip()
            clauses.append({
                "clause_id": f"Clause {clause_num}",
                "clause_num": int(clause_num),
                "header": header,
                "body": body,
                "full_text": full_clause,
            })
        return clauses

    def _load_and_index(self) -> None:
        """Reads tender document and builds the in-memory TF-IDF index."""
        if not self.corpus_path.exists():
            return
        with open(self.corpus_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        self.clauses = self._split_into_clauses(raw_text)
        if not self.clauses:
            return

        corpus_texts = [c["full_text"] for c in self.clauses]
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus_texts)

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Retrieves top-k most relevant clauses for a given query."""
        if not self.clauses or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # Sort indices by descending similarity
        ranked_indices = similarities.argsort()[::-1][:top_k]
        results = []
        for idx in ranked_indices:
            score = float(similarities[idx])
            clause_data = dict(self.clauses[idx])
            clause_data["score"] = score
            results.append(clause_data)
        return results

    def get_clause_by_id(self, clause_id: str) -> Optional[Dict[str, Any]]:
        """Direct clause lookup by identifier."""
        norm = clause_id.strip().lower()
        for c in self.clauses:
            if c["clause_id"].lower() == norm:
                return dict(c)
        return None
