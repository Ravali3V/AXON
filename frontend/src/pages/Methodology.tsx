import { useState } from "react";

const C = {
  bg:          "#0F1117",
  surface:     "#1A1D27",
  border:      "#2D3040",
  text:        "#E8E6E3",
  muted:       "#9B9A97",
  accent:      "#C8A97E",
  accentLight: "#E8D5B5",
  success:     "#4CAF50",
  warning:     "#FF9800",
  danger:      "#EF5350",
  info:        "#42A5F5",
} as const;

interface Criterion {
  name: string;
  points: number;
  basis: string;
  v1Note?: string;
}

interface Section {
  name: string;
  pointsPossible: number;
  color: string;
  criteria: Criterion[];
}

const RUBRIC: Section[] = [
  {
    name: "Listing Quality",
    pointsPossible: 30,
    color: "#E8622A",
    criteria: [
      { name: "Title Optimization",      points: 8, basis: "80–200 chars on each ASIN. Full points when ≥80% of ASINs meet the range." },
      { name: "Bullet Points",           points: 8, basis: "5 bullets present on each ASIN. Full points when ≥80% have 5." },
      { name: "Product Images",          points: 7, basis: "Avg images/ASIN: 7+=7pts · 5+=5.5pts · 3+=3.5pts · 1+=1.5pts." },
      { name: "Product Description",     points: 4, basis: "Description block >50 chars. Scored proportionally across ASINs." },
      { name: "Price Consistency",       points: 3, basis: "Coefficient of variation across prices: ≤10%=3 · ≤25%=2 · ≤40%=1 · >40%=0." },
    ],
  },
  {
    name: "Ratings & Reviews",
    pointsPossible: 20,
    color: "#3498DB",
    criteria: [
      { name: "Average Star Rating",      points: 8, basis: "4.5+=8 · 4.2+=6.5 · 4.0+=5 · 3.5+=3 · <3.5=1." },
      { name: "Review Volume",            points: 6, basis: "Avg reviews/ASIN: 500+=6 · 200+=5 · 100+=4 · 30+=2.5 · 5+=1." },
      { name: "Review Velocity",          points: 4, basis: "Catalog total reviews: 10K+ or avg 300+=4 · 3K+ or avg 100+=3 · 500+ or avg 25+=2." },
      { name: "Verified Purchase Ratio",  points: 2, basis: "Ratio of sampled reviews marked Verified Purchase: ≥80%=2 · ≥50%=1.5 · >0=0.5." },
    ],
  },
  {
    name: "Brand Presence",
    pointsPossible: 20,
    color: "#9B59B6",
    criteria: [
      { name: "Brand Store Exists",        points: 5, basis: "Binary — Brand Store URL discoverable from search or PDP byline." },
      { name: "Store Quality",             points: 5, basis: "Hero image (1.5) + pages ≥3 (1.5) + nav depth ≥4 (1) + product tiles ≥8 (1)." },
      { name: "A+ Content Coverage",       points: 5, basis: "% of ASINs with A+ modules. Full points at 100%." },
      { name: "Brand Story",               points: 3, basis: "% of ASINs with Brand Story carousel OR store About-Us detected." },
      { name: "Brand Registry Signal",     points: 2, basis: "Inferred from Brand Store + A+ presence: both=2 · either=1.5." },
    ],
  },
  {
    name: "Buy Box Health",
    pointsPossible: 15,
    color: "#27AE60",
    criteria: [
      { name: "Buy Box Ownership",  points: 10, basis: "% of ASINs where buy box is held by the brand or Amazon (FBA). ≥90%=10 · ≥70%=8 · ≥50%=5.5 · ≥25%=3 · >0=1.5." },
      { name: "3P Seller Risk",     points:  5, basis: "% of ASINs held by non-brand, non-Amazon sellers: 0%=5 · ≤10%=4 · ≤30%=3 · ≤50%=1.5 · >50%=0." },
    ],
  },
  {
    name: "Content Quality",
    pointsPossible: 15,
    color: "#F39C12",
    criteria: [
      { name: "BSR Performance",               points: 5, basis: "Avg BSR across catalog: <5K=5 · <20K=4 · <75K=3 · <200K=2 · else=1." },
      { name: "Video Coverage",                points: 5, basis: "% of ASINs with a product video: ≥80%=5 · ≥50%=4 · ≥25%=2.5 · >0=1." },
      { name: "A+ Module Depth",               points: 3, basis: "Avg A+ modules per A+-enabled ASIN: ≥6=3 · ≥3=2 · ≥1=1." },
      { name: "Enhanced Content Completeness", points: 2, basis: "% with A+ + Brand Story + Video all present: ≥70%=2 · ≥30%=1." },
    ],
  },
];

const GRADE_BANDS = [
  { label: "Thriving",  range: "85 – 100",  color: "#27AE60", sub: "Top performer — protect & scale" },
  { label: "Growing",   range: "70 – 84",   color: "#E8622A", sub: "Strong foundations detected" },
  { label: "Building",  range: "55 – 69",   color: "#3498DB", sub: "Solid progress underway" },
  { label: "Emerging",  range: "40 – 54",   color: "#E67E22", sub: "Significant opportunity ahead" },
  { label: "Untapped",  range: "0 – 39",    color: "#E74C3C", sub: "Major improvements needed" },
];

export function Methodology() {
  const [suggestion, setSuggestion] = useState("");
  const [sent, setSent] = useState(false);

  function sendSuggestion() {
    // eslint-disable-next-line no-console
    console.log("Rubric change suggestion:", suggestion);
    setSent(true);
  }

  const totalPoints = RUBRIC.reduce((a, s) => a + s.pointsPossible, 0);

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "2rem 1rem 5rem", fontFamily: "'DM Sans', sans-serif" }}>

      <h1 style={{ fontFamily: "'DM Serif Display', Georgia, serif", color: C.accent, marginBottom: "0.5rem" }}>
        Scoring Methodology
      </h1>
      <p style={{ color: C.muted, marginBottom: "2rem", lineHeight: 1.65 }}>
        AXON scores every brand against a <strong style={{ color: C.text }}>{totalPoints}-point rubric</strong> covering
        five sections. Each criterion receives one of three statuses: <strong>scored</strong> (measured from scraped data),{" "}
        <strong>warning</strong> (data missing — zero points), or <strong>na</strong> (not applicable — excluded from
        the denominator so the score stays on a fair 100-point scale).
      </p>

      {/* Grade Bands */}
      <h2 style={{ fontFamily: "'DM Serif Display', Georgia, serif", color: C.accentLight, marginBottom: "1rem" }}>
        Grade Bands
      </h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "10px", marginBottom: "2.5rem" }}>
        {GRADE_BANDS.map((g) => (
          <div key={g.label} style={{
            background: `${g.color}18`,
            border: `1px solid ${g.color}44`,
            borderRadius: "10px",
            padding: "14px 16px",
            textAlign: "center",
          }}>
            <div style={{ fontSize: "1.1rem", fontWeight: 800, color: g.color, marginBottom: "3px" }}>{g.label}</div>
            <div style={{ fontSize: "0.85rem", fontWeight: 600, color: C.text }}>{g.range}</div>
            <div style={{ fontSize: "0.72rem", color: C.muted, marginTop: "5px", lineHeight: 1.4 }}>{g.sub}</div>
          </div>
        ))}
      </div>

      {/* Rubric Sections */}
      <h2 style={{ fontFamily: "'DM Serif Display', Georgia, serif", color: C.accentLight, marginBottom: "1rem" }}>
        Full Rubric ({totalPoints} pts)
      </h2>
      {RUBRIC.map((section) => (
        <div key={section.name} style={{ marginBottom: "1.5rem", background: C.surface, border: `1px solid ${C.border}`, borderRadius: "10px", overflow: "hidden" }}>
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "0.75rem 1.25rem",
            borderLeft: `4px solid ${section.color}`,
            background: `${section.color}12`,
          }}>
            <h3 style={{ margin: 0, color: section.color, fontSize: "1rem" }}>{section.name}</h3>
            <strong style={{ color: section.color }}>{section.pointsPossible} pts</strong>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                <th style={{ textAlign: "left", padding: "0.5rem 1.25rem", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.08em", color: C.muted, fontWeight: 700 }}>Criterion</th>
                <th style={{ width: "60px", padding: "0.5rem 0.5rem", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.08em", color: C.muted, fontWeight: 700 }}>Pts</th>
                <th style={{ textAlign: "left", padding: "0.5rem 1.25rem 0.5rem 0", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.08em", color: C.muted, fontWeight: 700 }}>Scoring Basis</th>
              </tr>
            </thead>
            <tbody>
              {section.criteria.map((c, i) => (
                <tr key={c.name} style={{ borderBottom: i < section.criteria.length - 1 ? `1px solid ${C.border}` : "none" }}>
                  <td style={{ padding: "0.6rem 1.25rem", color: C.text, fontSize: "0.87rem", fontWeight: 500 }}>{c.name}</td>
                  <td style={{ padding: "0.6rem 0.5rem", color: section.color, fontWeight: 700, fontSize: "0.87rem" }}>{c.points}</td>
                  <td style={{ padding: "0.6rem 1.25rem 0.6rem 0", color: C.muted, fontSize: "0.83rem", lineHeight: 1.55 }}>
                    {c.basis}
                    {c.v1Note && (
                      <span style={{ marginLeft: "0.4rem", fontSize: "0.75rem", color: C.warning, fontWeight: 600 }}>
                        {c.v1Note}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {/* Suggest a Change */}
      <h2 style={{ fontFamily: "'DM Serif Display', Georgia, serif", color: C.accentLight, marginBottom: "0.5rem", marginTop: "2rem" }}>
        Suggest a Rubric Change
      </h2>
      <p style={{ color: C.muted, marginBottom: "0.75rem" }}>
        See something that should score differently? Tell us.
      </p>
      <textarea
        value={suggestion}
        onChange={(e) => setSuggestion(e.target.value)}
        rows={5}
        style={{
          width: "100%", padding: "0.6rem",
          background: C.surface, color: C.text,
          border: `1px solid ${C.border}`, borderRadius: "6px",
          fontFamily: "inherit", fontSize: "0.95rem",
        }}
        placeholder="e.g. Brand Story should weight About-Us depth more heavily because…"
      />
      <div style={{ marginTop: "0.5rem" }}>
        <button
          onClick={sendSuggestion}
          disabled={!suggestion.trim() || sent}
          style={{
            padding: "0.5rem 1rem",
            background: sent ? C.surface : C.accent,
            color: sent ? C.muted : C.bg,
            border: "none", borderRadius: "24px",
            cursor: sent ? "default" : "pointer", fontWeight: 600,
          }}
        >
          {sent ? "Thanks — logged." : "Send suggestion"}
        </button>
      </div>
    </div>
  );
}
