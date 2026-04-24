# AXON — User Guide

For the AXON operator (currently: the founding team). Walks through the v1 Brand Audit Tier 1 flow.

---

## Running a Tier 1 Brand Audit (v1)

### 1. Open the AXON app
- Local dev: <http://localhost:5173>
- Prod: TBD (provisioned at T-02)

### 2. Start an audit
On the **Input** screen:
- Type the exact brand name as it appears on Amazon.
- Click **Start audit**.

### 3. Wait on the Progress screen
- Live stage indicator: Resolving brand → Discovering ASINs → Scraping PDPs → Scraping Brand Store → Scraping reviews → Scoring → Enriching with Claude → Rendering PDF.
- ETA updates as stages complete.
- Realistic runtime: 10–30 minutes depending on brand size. Walk away; the Progress screen will update live.

### 4. Review the report
When complete, the **Report Viewer** opens automatically. You see:
- Overall grade + total score out of 100.
- Per-section breakdown.
- Per-criterion scores with `scored` / `na` / `warning` status indicators.
- Findings grouped by type: strengths, weaknesses, recommendations, quick wins.
- Per-ASIN drill-down.
- **Download PDF** button (same content, print-ready).

### 5. Understand the scoring
Click **Methodology** in the top nav to see the full rubric: each section, each criterion, the point weight, and the thresholds. Use the **Suggest a rubric change** textarea at the bottom if a score feels wrong — it emails the team.

### 6. Correct scraped values and re-score
If the scraper got something wrong (e.g. miscounted images), open the audit's **Manual Override** screen:
- Edit any scraped brand-level or per-ASIN value.
- Click **Re-score**. This runs scoring only (no new scrape), saves your corrections, and increments the audit version.
- The Report Viewer updates to show the re-scored result.

---

## Known v1 Limitations

- **No login.** All audits attribute to "AXON Internal." Login will ship in v1.1.
- **No historical data.** BSR trend and pricing consistency show as `warning — insufficient data`. They will unlock once historical tracking is added (deferred decision).
- **Large brands may take 30+ min.** No ASIN cap by default. Use the Override + Re-score flow if the scrape picks up unrelated products.
- **CAPTCHA failures degrade to `warning`.** After 3 proxy rotations, the affected section is marked `warning` rather than failing the whole audit.
