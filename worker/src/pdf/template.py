"""Customer-facing HTML template for the Amazon Brand Audit PDF.

Light cream theme — gold accents, dark charcoal text, prominent brand imagery.
All CSS inline — renders correctly in headless Chromium print-to-PDF.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

# Grade palette — tuned for light background
GRADE_CONFIG = {
    "Thriving":  {"color": "#2A9D5C", "bg": "#E7F5EC", "icon": "▲"},
    "Growing":   {"color": "#D15A1C", "bg": "#FBE9DD", "icon": "●"},
    "Building":  {"color": "#2980B9", "bg": "#E3EFF8", "icon": "◆"},
    "Emerging":  {"color": "#D17A1C", "bg": "#FBEDDC", "icon": "◑"},
    "Untapped":  {"color": "#C0392B", "bg": "#F8E1DD", "icon": "○"},
}

SECTION_COLORS = {
    "Listing Quality":    "#D15A1C",
    "Ratings & Reviews":  "#2980B9",
    "Brand Presence":     "#8E44AD",
    "Buy Box Health":     "#2A9D5C",
    "Content Quality":    "#D4A017",
}


def render_report_html(payload: dict[str, Any]) -> str:
    brand = html.escape(str(payload.get("brand_name", "")))
    grade = payload.get("grade", "Untapped")
    grade_cfg = GRADE_CONFIG.get(grade, GRADE_CONFIG["Untapped"])
    grade_color = grade_cfg["color"]
    grade_bg = grade_cfg["bg"]

    earned = payload.get("total_earned", 0)
    possible = payload.get("total_possible", 100)
    pct = payload.get("percentage", 0)
    generated_full = datetime.utcnow().strftime("%B %d, %Y")

    narrative = html.escape(payload.get("narrative", "")).replace("\n", "<br>")
    strengths = payload.get("strengths", [])
    weaknesses = payload.get("weaknesses", [])
    watch_closely = sorted(weaknesses, key=lambda w: w.get("priority", 5))
    opportunities = payload.get("recommendations", [])
    quick_wins = payload.get("quick_wins", [])
    sections = [s for s in payload.get("sections", []) if s["name"] != "Others"]
    asins = payload.get("asins", [])

    # Top stats
    total_asins = len(asins)
    avg_rating = _avg_rating(asins)
    total_reviews = sum(a.get("review_count") or 0 for a in asins)
    buybox_pct = _buybox_pct(asins, payload.get("brand_name", ""))
    categories = len({a.get("bsr_category") for a in asins if a.get("bsr_category")})

    # Brand images — up to 8, ranked by review count
    top_asins = sorted(
        [a for a in asins if a.get("main_image_url")],
        key=lambda a: a.get("review_count") or 0,
        reverse=True,
    )[:8]

    all_recs = opportunities + quick_wins
    the_one_thing = all_recs[0]["text"] if all_recs else None

    about_text = payload.get("about_us_text") or ""

    # Build sections
    brand_images_html = _render_brand_images_strip(top_asins)
    brand_intro_html = _render_brand_intro(about_text)
    score_breakdown_html = _render_score_breakdown(sections)
    findings_html = _render_findings_columns(strengths, watch_closely, opportunities)
    top_asins_cards_html = _render_top_asin_cards(top_asins[:4])
    one_thing_html = _render_one_thing(the_one_thing)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Brand Audit — {brand}</title>
<style>
  @page {{ size: Letter; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Helvetica Neue", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: #FAF7F0;
    color: #1F2430;
    font-size: 10pt;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: inherit; text-decoration: none; }}

  /* ============================================================
     COVER
  ============================================================ */
  .cover {{
    page-break-after: always;
    min-height: 11in;
    background: #FAF7F0;
    padding: 0;
    position: relative;
    display: flex;
    flex-direction: column;
  }}

  /* Top accent band */
  .cover-accent-top {{
    height: 14pt;
    background: linear-gradient(90deg, #C8A97E 0%, #D4B896 50%, #C8A97E 100%);
  }}

  .cover-header {{
    padding: 24pt 44pt 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .cover-badge {{
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #C8A97E;
    border: 1pt solid #C8A97E;
    padding: 5pt 14pt;
    border-radius: 2pt;
  }}
  .cover-prepared {{
    font-size: 8pt;
    color: #8B8478;
    letter-spacing: 0.06em;
  }}
  .cover-prepared strong {{
    color: #1F2430;
    font-weight: 700;
  }}

  .cover-body {{
    padding: 40pt 44pt 0;
    flex: 1;
  }}
  .cover-brand-label {{
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #C8A97E;
    margin-bottom: 14pt;
  }}
  .cover-brand-name {{
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 56pt;
    font-weight: 400;
    color: #1F2430;
    letter-spacing: -1pt;
    line-height: 1.02;
    margin-bottom: 12pt;
  }}
  .cover-subtitle {{
    font-size: 11pt;
    color: #5A5648;
    line-height: 1.65;
    max-width: 500pt;
    margin-bottom: 22pt;
  }}

  /* Brand image strip — prominent, horizontal */
  .brand-images {{
    margin-bottom: 24pt;
  }}
  .brand-images-label {{
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #8B8478;
    margin-bottom: 10pt;
    padding-bottom: 6pt;
    border-bottom: 1pt solid #E6DFCF;
  }}
  .image-strip {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10pt;
  }}
  .image-tile {{
    background: #FFFFFF;
    border: 1pt solid #E6DFCF;
    border-radius: 6pt;
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }}
  .image-tile img {{
    width: 100%;
    height: 100%;
    object-fit: contain;
    padding: 8pt;
  }}

  /* Stats strip */
  .stats-strip {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0;
    margin-bottom: 26pt;
    border-top: 1pt solid #E6DFCF;
    border-bottom: 1pt solid #E6DFCF;
  }}
  .stat-pill {{
    padding: 14pt 12pt;
    border-right: 1pt solid #E6DFCF;
    text-align: center;
  }}
  .stat-pill:last-child {{ border-right: none; }}
  .stat-pill-val {{
    font-family: "Georgia", serif;
    font-size: 20pt;
    font-weight: 400;
    color: #1F2430;
    line-height: 1;
    margin-bottom: 4pt;
  }}
  .stat-pill-val.accent {{ color: #C8A97E; }}
  .stat-pill-lbl {{
    font-size: 7pt;
    color: #8B8478;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 600;
  }}

  /* Score + grade row */
  .score-row {{
    display: flex;
    gap: 22pt;
    align-items: center;
    padding: 20pt 22pt;
    background: #FFFFFF;
    border: 1pt solid #E6DFCF;
    border-radius: 8pt;
  }}
  .score-circle-wrap {{
    width: 120pt;
    height: 120pt;
    border-radius: 50%;
    border: 5pt solid {grade_color};
    background: {grade_bg};
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }}
  .score-circle-num {{
    font-family: "Georgia", serif;
    font-size: 42pt;
    font-weight: 400;
    color: #1F2430;
    line-height: 1;
  }}
  .score-circle-denom {{
    font-size: 9pt;
    color: #8B8478;
    margin-top: 2pt;
    letter-spacing: 0.04em;
  }}
  .score-text {{
    flex: 1;
  }}
  .grade-title {{
    font-family: "Georgia", serif;
    font-size: 26pt;
    font-weight: 400;
    color: {grade_color};
    margin-bottom: 4pt;
    letter-spacing: -0.5pt;
  }}
  .grade-sub {{
    font-size: 10pt;
    color: #5A5648;
    line-height: 1.55;
  }}

  .cover-footer {{
    margin-top: auto;
    padding: 16pt 44pt;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1pt solid #E6DFCF;
    background: #F4EFDF;
  }}
  .cover-footer-brand {{
    font-size: 7.5pt;
    color: #8B8478;
    letter-spacing: 0.05em;
  }}
  .cover-footer-page {{
    font-size: 7.5pt;
    color: #A8A293;
  }}

  /* ============================================================
     INNER PAGE
  ============================================================ */
  .page {{
    page-break-before: always;
    min-height: 11in;
    background: #FAF7F0;
    padding: 26pt 44pt 0;
    display: flex;
    flex-direction: column;
  }}
  .page-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding-bottom: 8pt;
    border-bottom: 1pt solid #E6DFCF;
    margin-bottom: 16pt;
  }}
  .page-header-brand {{
    font-size: 9pt;
    color: #5A5648;
    font-weight: 600;
    letter-spacing: 0.05em;
  }}
  .page-header-title {{
    font-size: 8pt;
    color: #C8A97E;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }}
  .page-title {{
    font-family: "Georgia", serif;
    font-size: 22pt;
    font-weight: 400;
    color: #1F2430;
    margin-bottom: 3pt;
    letter-spacing: -0.5pt;
    line-height: 1.15;
  }}
  .page-title-sub {{
    font-size: 9pt;
    color: #8B8478;
    margin-bottom: 16pt;
    font-style: italic;
  }}

  .section-label {{
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #C8A97E;
    margin-bottom: 10pt;
    padding-bottom: 5pt;
    border-bottom: 1pt solid #E6DFCF;
  }}

  /* Score breakdown table */
  .score-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 14pt;
  }}
  .score-table th {{
    font-size: 7.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #8B8478;
    padding: 0 0 8pt 0;
    text-align: left;
    border-bottom: 1.5pt solid #C8A97E;
  }}
  .score-table th:last-child {{ text-align: right; }}
  .score-table td {{
    padding: 10pt 0;
    border-bottom: 1pt solid #E6DFCF;
    vertical-align: middle;
  }}
  .score-table tr:last-child td {{ border-bottom: none; }}
  .st-section-name {{
    font-size: 10pt;
    font-weight: 600;
    width: 32%;
  }}
  .st-bar-cell {{
    width: 42%;
    padding-right: 16pt;
  }}
  .st-bar-bg {{
    background: #EBE4D1;
    border-radius: 4pt;
    height: 8pt;
    overflow: hidden;
  }}
  .st-bar-fill {{
    height: 8pt;
    border-radius: 4pt;
  }}
  .st-score {{
    font-size: 11pt;
    font-weight: 700;
    text-align: right;
    font-family: "Georgia", serif;
    white-space: nowrap;
  }}

  /* Narrative */
  .narrative-box {{
    background: #FFFFFF;
    border-left: 3pt solid #C8A97E;
    border-radius: 0 6pt 6pt 0;
    padding: 11pt 16pt;
    margin-bottom: 16pt;
    font-size: 9.5pt;
    color: #2D3142;
    line-height: 1.6;
    font-style: italic;
  }}

  /* Top ASIN cards */
  .asin-cards-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10pt;
    margin-bottom: 22pt;
  }}
  .asin-card {{
    background: #FFFFFF;
    border: 1pt solid #E6DFCF;
    border-radius: 7pt;
    overflow: hidden;
  }}
  .asin-card-img {{
    width: 100%;
    aspect-ratio: 1;
    background: #FAF7F0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    border-bottom: 1pt solid #E6DFCF;
  }}
  .asin-card-img img {{
    width: 100%;
    height: 100%;
    object-fit: contain;
    padding: 8pt;
  }}
  .asin-card-body {{ padding: 8pt 10pt; }}
  .asin-card-asin {{
    font-size: 7pt;
    color: #A8A293;
    font-family: monospace;
    margin-bottom: 3pt;
  }}
  .asin-card-title {{
    font-size: 8pt;
    color: #2D3142;
    line-height: 1.4;
    margin-bottom: 6pt;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}
  .asin-card-meta {{
    display: flex;
    gap: 10pt;
    font-size: 7.5pt;
    color: #8B8478;
  }}
  .asin-card-meta strong {{
    color: #1F2430;
    font-weight: 700;
  }}

  /* Findings columns */
  .findings-header {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10pt;
    margin-bottom: 10pt;
  }}
  .findings-col-header {{
    font-size: 8.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    padding-bottom: 7pt;
    border-bottom: 2pt solid;
    text-align: center;
  }}
  .findings-col-header.green  {{ color: #2A9D5C; border-color: #2A9D5C; }}
  .findings-col-header.orange {{ color: #D15A1C; border-color: #D15A1C; }}
  .findings-col-header.blue   {{ color: #2980B9; border-color: #2980B9; }}

  .findings-columns {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8pt;
    margin-bottom: 14pt;
  }}
  .findings-col {{
    display: flex;
    flex-direction: column;
    gap: 5pt;
  }}
  .finding-item {{
    display: flex;
    align-items: flex-start;
    gap: 6pt;
    font-size: 8pt;
    color: #2D3142;
    line-height: 1.45;
    padding: 6pt 9pt;
    background: #FFFFFF;
    border: 1pt solid #E6DFCF;
    border-radius: 5pt;
  }}
  .finding-icon {{
    font-size: 10pt;
    flex-shrink: 0;
    font-weight: 700;
    line-height: 1.2;
  }}
  .finding-icon.green  {{ color: #2A9D5C; }}
  .finding-icon.orange {{ color: #D15A1C; }}
  .finding-icon.blue   {{ color: #2980B9; }}
  .finding-text-bold {{ font-weight: 700; color: #1F2430; }}

  /* One Thing */
  .one-thing-box {{
    background: #F8F1E0;
    border: 1pt solid #C8A97E;
    border-radius: 8pt;
    padding: 14pt 20pt;
    margin-bottom: 14pt;
  }}
  .one-thing-label {{
    font-size: 7.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: #C8A97E;
    margin-bottom: 8pt;
  }}
  .one-thing-text {{
    font-family: "Georgia", serif;
    font-size: 12pt;
    font-weight: 400;
    color: #1F2430;
    line-height: 1.5;
    font-style: italic;
  }}

  /* CTA */
  .cta-box {{
    background: #1F2430;
    color: #FFFFFF;
    border-radius: 8pt;
    padding: 20pt 24pt;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: auto;
  }}
  .cta-title {{
    font-family: "Georgia", serif;
    font-size: 13pt;
    font-weight: 400;
    color: #FFFFFF;
    margin-bottom: 5pt;
  }}
  .cta-subtitle {{
    font-size: 8.5pt;
    color: rgba(255,255,255,0.65);
    line-height: 1.55;
    max-width: 340pt;
  }}
  .cta-btn {{
    background: #C8A97E;
    color: #1F2430;
    font-size: 9pt;
    font-weight: 700;
    padding: 11pt 22pt;
    border-radius: 4pt;
    white-space: nowrap;
    flex-shrink: 0;
    margin-left: 20pt;
    letter-spacing: 0.04em;
  }}

  /* Page footer */
  .page-footer {{
    padding-top: 14pt;
    margin-top: 18pt;
    border-top: 1pt solid #E6DFCF;
    display: flex;
    justify-content: space-between;
    font-size: 7.5pt;
    color: #A8A293;
  }}
</style>
</head>
<body>

<!-- PAGE 1 — COVER -->
<div class="cover">
  <div class="cover-accent-top"></div>

  <div class="cover-header">
    <div class="cover-badge">Brand Audit Report</div>
    <div class="cover-prepared">Prepared by <strong>Aitomic</strong></div>
  </div>

  <div class="cover-body">
    <div class="cover-brand-name">{brand}</div>

    {brand_intro_html}

    {brand_images_html}

    <div class="stats-strip">
      <div class="stat-pill">
        <div class="stat-pill-val accent">{total_asins}</div>
        <div class="stat-pill-lbl">ASINs</div>
      </div>
      <div class="stat-pill">
        <div class="stat-pill-val">{categories or "—"}</div>
        <div class="stat-pill-lbl">Categories</div>
      </div>
      <div class="stat-pill">
        <div class="stat-pill-val">{avg_rating}</div>
        <div class="stat-pill-lbl">Avg Rating</div>
      </div>
      <div class="stat-pill">
        <div class="stat-pill-val">{_fmt_number(total_reviews)}</div>
        <div class="stat-pill-lbl">Total Reviews</div>
      </div>
      <div class="stat-pill">
        <div class="stat-pill-val">{buybox_pct}%</div>
        <div class="stat-pill-lbl">Buy Box</div>
      </div>
    </div>

    <div class="score-row">
      <div class="score-circle-wrap">
        <div class="score-circle-num">{int(earned)}</div>
        <div class="score-circle-denom">/ {int(possible)}</div>
      </div>
      <div class="score-text">
        <div class="grade-title">{html.escape(grade)}</div>
        <div class="grade-sub">
          {"Top performer — protect & scale" if pct >= 85 else
           "Strong foundations detected — build momentum" if pct >= 70 else
           "Solid progress underway — focus on gaps" if pct >= 55 else
           "Significant opportunity ahead — prioritise quick wins" if pct >= 40 else
           "Major improvements needed — start with fundamentals"}
        </div>
      </div>
    </div>
  </div>

  <div class="cover-footer">
    <div class="cover-footer-brand">Aitomic · {generated_full}</div>
    <div class="cover-footer-page">Confidential — Prepared exclusively for {brand} · Page 1 of 2</div>
  </div>
</div>

<!-- PAGE 2 — SCORE + FINDINGS -->
<div class="page">
  <div class="page-header">
    <div class="page-header-brand">{brand}</div>
    <div class="page-header-title">Score · Findings · Opportunities</div>
  </div>

  <div class="page-title">Score Breakdown</div>
  <div class="page-title-sub">How {brand} performs across the five audit pillars</div>

  {score_breakdown_html}

  {f'<div class="narrative-box">{narrative}</div>' if narrative else ""}

  <div class="section-label">Detailed Findings &amp; Growth Opportunities</div>

  <div class="findings-header">
    <div class="findings-col-header green">✦ Strengths</div>
    <div class="findings-col-header orange">⚑ Watch Closely</div>
    <div class="findings-col-header blue">■ Opportunities</div>
  </div>

  {findings_html}

  {one_thing_html}

  <div class="cta-box">
    <div>
      <div class="cta-title">Want the full picture?</div>
      <div class="cta-subtitle">
        This report covers publicly available data across your brand's Amazon presence.
        Our Tier 2 audit maps SP-API metrics, keyword rank, competitor benchmarking,
        and includes a dedicated account strategy session.
      </div>
    </div>
    <div class="cta-btn">Let's walk you through this →</div>
  </div>

  <div class="page-footer">
    <span>Aitomic · Confidential — Prepared exclusively for {brand}</span>
    <span>Page 2 of 2</span>
  </div>
</div>

</body>
</html>"""


# ============================================================
# Helper renderers
# ============================================================

def _render_brand_intro(text: str) -> str:
    if not text:
        return ""
    snippet = html.escape(text[:360])
    if len(text) > 360:
        snippet += "…"
    return f'<div class="cover-subtitle">{snippet}</div>'


def _render_brand_images_strip(top_asins: list[dict[str, Any]]) -> str:
    if not top_asins:
        return ""
    tiles = ""
    for asin in top_asins[:4]:
        img_url = html.escape(asin.get("main_image_url") or "")
        if img_url:
            tiles += f'<div class="image-tile"><img src="{img_url}" alt="" /></div>'
    if not tiles:
        return ""
    return f"""<div class="brand-images">
  <div class="brand-images-label">Featured Products</div>
  <div class="image-strip">{tiles}</div>
</div>"""


def _render_score_breakdown(sections: list[dict[str, Any]]) -> str:
    if not sections:
        return '<p style="color:#8B8478;font-size:9pt">No section scores available.</p>'
    rows = ""
    for s in sections:
        name = html.escape(s["name"])
        earned = float(s.get("earned", 0))
        possible = float(s.get("possible", 1))
        pct = (earned / possible * 100) if possible > 0 else 0
        color = SECTION_COLORS.get(s["name"], "#C8A97E")
        bar_width = f"{max(pct, 2):.0f}%"
        score_str = f'{earned:.0f}<span style="color:#A8A293;font-size:8pt;font-weight:400">/{possible:.0f}</span>'
        rows += f"""<tr>
  <td class="st-section-name" style="color:{color}">{name}</td>
  <td class="st-bar-cell">
    <div class="st-bar-bg">
      <div class="st-bar-fill" style="width:{bar_width};background:{color}"></div>
    </div>
  </td>
  <td class="st-score" style="color:{color}">{score_str}</td>
</tr>"""
    return f"""<table class="score-table">
  <thead>
    <tr>
      <th>Section</th>
      <th>Performance</th>
      <th style="text-align:right">Score</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""


def _render_top_asin_cards(top_asins: list[dict[str, Any]]) -> str:
    if not top_asins:
        return ""
    cards = ""
    for asin in top_asins[:4]:
        img_url = html.escape(asin.get("main_image_url") or "")
        img_html = f'<img src="{img_url}" alt="" />' if img_url else ""
        title = html.escape(str(asin.get("title", "") or "")[:70])
        asin_code = html.escape(str(asin.get("asin", "")))
        rating = asin.get("rating") or "—"
        reviews = _fmt_number(asin.get("review_count") or 0)
        cards += f"""<div class="asin-card">
  <div class="asin-card-img">{img_html}</div>
  <div class="asin-card-body">
    <div class="asin-card-asin">{asin_code}</div>
    <div class="asin-card-title">{title}</div>
    <div class="asin-card-meta">
      <div><strong>{rating}</strong>★</div>
      <div><strong>{reviews}</strong> reviews</div>
    </div>
  </div>
</div>"""
    return f'<div class="asin-cards-grid">{cards}</div>'


def _render_findings_columns(
    strengths: list[dict[str, Any]],
    watch_closely: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
) -> str:
    def _items(items: list[dict[str, Any]], icon: str, icon_class: str, max_items: int = 5) -> str:
        if not items:
            return f'<div class="finding-item"><span class="finding-icon {icon_class}">{icon}</span><span style="color:#A8A293;font-style:italic">None identified</span></div>'
        html_out = ""
        for item in items[:max_items]:
            text = html.escape(item.get("text", ""))
            if ":" in text:
                parts = text.split(":", 1)
                text = f'<span class="finding-text-bold">{parts[0]}:</span>{parts[1]}'
            html_out += f'<div class="finding-item"><span class="finding-icon {icon_class}">{icon}</span><span>{text}</span></div>'
        return html_out

    return f"""<div class="findings-columns">
  <div class="findings-col">{_items(strengths, "✓", "green")}</div>
  <div class="findings-col">{_items(watch_closely, "!", "orange")}</div>
  <div class="findings-col">{_items(opportunities, "→", "blue")}</div>
</div>"""


def _render_one_thing(text: str | None) -> str:
    if not text:
        return ""
    return f"""<div class="one-thing-box">
  <div class="one-thing-label">The One Thing · Highest Impact Action</div>
  <div class="one-thing-text">{html.escape(text)}</div>
</div>"""


# ============================================================
# Utilities
# ============================================================

def _avg_rating(asins: list[dict[str, Any]]) -> str:
    rated = [float(a["rating"]) for a in asins if a.get("rating") is not None]
    if not rated:
        return "—"
    return f"{sum(rated)/len(rated):.1f}★"


def _buybox_pct(asins: list[dict[str, Any]], brand_name: str) -> int:
    if not asins:
        return 0
    brand_lower = brand_name.lower().strip()
    brand_words = {w for w in brand_lower.split() if len(w) >= 5}

    def _healthy(seller: Any) -> bool:
        if not seller:
            return False
        sl = str(seller).lower()
        if brand_lower in sl:
            return True
        if "amazon" in sl:
            return True
        return bool(brand_words and any(w in sl for w in brand_words))

    owned = sum(1 for a in asins if _healthy(a.get("buybox_seller")))
    return round(owned / len(asins) * 100)


def _fmt_number(n: int | None) -> str:
    if not n:
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)
