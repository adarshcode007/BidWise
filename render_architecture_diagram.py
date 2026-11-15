"""Renders high-resolution architecture diagram to docs/architecture.png."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def render_diagram():
    # Dimensions
    width = 1400
    height = 950
    bg_color = (250, 252, 255)

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Use standard default or truetype font if available
    try:
        title_font = ImageFont.truetype("arial.ttf", 26)
        header_font = ImageFont.truetype("arial.ttf", 18)
        body_font = ImageFont.truetype("arial.ttf", 14)
        small_font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Color Palette
    agent_bg = (224, 242, 254)       # Light blue
    agent_border = (2, 132, 199)      # Darker blue
    agent_text = (3, 105, 161)

    state_bg = (254, 243, 199)       # Warm amber
    state_border = (217, 119, 6)
    state_text = (146, 64, 14)

    storage_bg = (243, 232, 255)     # Purple
    storage_border = (147, 51, 234)
    storage_text = (107, 33, 168)

    action_bg = (220, 252, 231)      # Emerald green
    action_border = (22, 163, 74)
    action_text = (21, 128, 61)

    disq_bg = (254, 226, 226)        # Soft red
    disq_border = (220, 38, 38)
    disq_text = (185, 28, 28)

    arrow_color = (71, 85, 105)

    def draw_box(x, y, w, h, bg, border, title, subtitle="", radius=10, text_color=(30, 41, 59)):
        draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=bg, outline=border, width=2)
        # Draw title
        draw.text((x + 15, y + 12), title, fill=text_color, font=header_font)
        if subtitle:
            draw.text((x + 15, y + 36), subtitle, fill=(100, 116, 139), font=small_font)

    def draw_arrow(x1, y1, x2, y2, label=""):
        draw.line([x1, y1, x2, y2], fill=arrow_color, width=2)
        # Arrowhead
        import math
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_len = 10
        px1 = x2 - arrow_len * math.cos(angle - math.pi / 6)
        py1 = y2 - arrow_len * math.sin(angle - math.pi / 6)
        px2 = x2 - arrow_len * math.cos(angle + math.pi / 6)
        py2 = y2 - arrow_len * math.sin(angle + math.pi / 6)
        draw.polygon([(x2, y2), (px1, py1), (px2, py2)], fill=arrow_color)
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 12
            draw.text((mx + 5, my), label, fill=(71, 85, 105), font=small_font)

    # 1. Title Banner
    draw.text((40, 25), "BidWise Multi-Agent Tender Evaluation System", fill=(15, 23, 42), font=title_font)
    draw.text((40, 60), "Architecture: Fan-Out / Fan-In Parallel Bid Scoring | Semantic Kernel (Python)", fill=(100, 116, 139), font=body_font)

    # 2. Input Corpus (Left)
    draw_box(40, 120, 250, 90, storage_bg, storage_border, "Tender Document", "data/tender.txt (Clauses 1-7)", text_color=storage_text)
    draw_box(40, 230, 250, 90, storage_bg, storage_border, "Technical Rubric", "data/rubric.json (Criteria benchmarks)", text_color=storage_text)
    draw_box(40, 340, 250, 110, storage_bg, storage_border, "Vendor Proposals", "data/bids/bid_A..D.txt\nPrices, Delivery, Certifications", text_color=storage_text)

    # 3. Stage 1: Criteria Agent (RAG)
    draw_box(350, 120, 280, 90, agent_bg, agent_border, "Criteria Agent (RAG)", "retrieve_clauses(), parse_weights()", text_color=agent_text)
    draw_arrow(290, 165, 350, 165, "TF-IDF Query")

    # 4. Central Shared State & Run Log
    draw_box(700, 110, 300, 110, state_bg, state_border, "Shared Scorecard", "dataclass with asyncio.Lock\nCriteria, Bids Slices, Events, Winner", text_color=state_text)
    draw_box(1050, 110, 300, 110, state_bg, state_border, "Append-Only Run Log", "logs/run_log.jsonl (mode='a')\nImmutable event & tool audit trail", text_color=state_text)

    draw_arrow(630, 165, 700, 165, "Criteria Slice")
    draw_arrow(1000, 165, 1050, 165, "Audit Events")

    # 5. Fan-Out Parallel Bid Scorers (Middle Tier)
    draw.text((40, 480), "PARALLEL FAN-OUT BID EVALUATION (asyncio.gather)", fill=(30, 41, 59), font=header_font)
    draw_arrow(800, 220, 800, 470, "Dispatch Bids")

    # Four Bid Worker Lanes
    bid_y = 520
    bid_w = 290
    bid_h = 160

    # Bid A
    draw_box(40, bid_y, bid_w, bid_h, agent_bg, agent_border, "Bid A Worker", "Alpha Networks ($125k, 45d)\n- Compliance: PASS\n- Tech: 40/40, Exp: 20/20\n- Commercial: 24.00 (Total: 91.00)", text_color=agent_text)

    # Bid B
    draw_box(370, bid_y, bid_w, bid_h, agent_bg, agent_border, "Bid B Worker", "Beta Infra ($100k - Lowest, 60d)\n- Compliance: PASS\n- Tech: 25.5/40, Exp: 12/20\n- Commercial: 30.00 (Total: 72.50)", text_color=agent_text)

    # Bid C (Disqualified)
    draw_box(700, bid_y, bid_w, bid_h, disq_bg, disq_border, "Bid C Worker (DISQUALIFIED)", "Gamma Systems ($110k, 30d)\n- Missing 'EMD Receipt'\n- Disqualified by ComplianceAgent\n- Excluded from financial ranking", text_color=disq_text)

    # Bid D (Tie-Break Contender)
    draw_box(1030, bid_y, bid_w, bid_h, agent_bg, agent_border, "Bid D Worker", "Delta Comm ($115k, 20d)\n- Compliance: PASS\n- Tech: 40/40, Exp: 16/20\n- Commercial: 26.09 (Total: 92.09)", text_color=agent_text)

    # 6. Fan-In: Award Manager & Tie-Break Agent (Bottom Tier)
    award_y = 740
    draw_arrow(515, 680, 515, award_y, "Fan-In Slices")
    draw_arrow(1175, 680, 550, award_y, "")

    draw_box(400, award_y, 290, 120, agent_bg, agent_border, "Award Manager (Fan-In)", "apply_weights(), rank_bids()\nFilters Bid C, normalizes prices,\ncalculates totals & initial ranks", text_color=agent_text)

    draw_arrow(690, award_y + 60, 750, award_y + 60, "Check Margin <= 2.0")

    draw_box(750, award_y, 280, 120, action_bg, action_border, "Tie-Break Agent", "detect_ties(), apply_secondary()\nDiff = 1.09 <= 2.0 margin\nBid D wins: 20 days vs 45 days!", text_color=action_text)

    draw_arrow(1030, award_y + 60, 1090, award_y + 60, "Award Decision")

    draw_box(1090, award_y, 270, 120, storage_bg, storage_border, "Final Output Deliverables", "- output/report.md\n- output/scorecard.json\nWinner: bid_D (Delta Comm)", text_color=storage_text)

    # Save PNG
    output_png = Path("docs/architecture.png")
    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png, "PNG")
    print(f"Rendered architecture diagram to {output_png} ({output_png.stat().st_size} bytes)")


if __name__ == "__main__":
    render_diagram()
