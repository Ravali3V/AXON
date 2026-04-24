import { useState, useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { getAudit, downloadAuditPdf, type AuditDetailResponse } from "../lib/api";

// Palette — matches the Widdop reference design exactly
const C = {
  bg:          "#0F1117",
  surface:     "#1A1D27",
  surface2:    "#23262F",
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

const OTHERS_SECTION = "Others";
type TabId = "overview" | "findings" | "recommendations" | "scores" | "asins";

const GRADE_CONFIG: Record<string, { color: string; label: string; sub: string }> = {
  Thriving:  { color: "#27AE60", label: "Thriving",  sub: "Top performer — protect & scale" },
  Growing:   { color: "#E8622A", label: "Growing",   sub: "Strong foundations detected" },
  Building:  { color: "#3498DB", label: "Building",  sub: "Solid progress underway" },
  Emerging:  { color: "#E67E22", label: "Emerging",  sub: "Significant opportunity ahead" },
  Untapped:  { color: "#E74C3C", label: "Untapped",  sub: "Major improvements needed" },
};

export function Report() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<AuditDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const navRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    getAudit(id)
      .then(setData)
      .catch((err) => setError((err as Error).message));
  }, [id]);

  async function handleDownloadPdf() {
    if (!id || !data) return;
    setDownloading(true);
    try {
      await downloadAuditPdf(id, data.audit.brandName);
    } catch (err) {
      alert(`Download failed: ${(err as Error).message}`);
    } finally {
      setDownloading(false);
    }
  }

  function toggleSection(name: string) {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  if (error) {
    return (
      <div style={s.centerPage}>
        <div style={s.errorCard}>
          <div style={{ color: C.danger, fontSize: "1.1rem", marginBottom: "0.5rem" }}>
            Failed to load report
          </div>
          <div style={{ color: C.muted, marginBottom: "1rem" }}>{error}</div>
          <Link to="/" style={s.linkBtn}>← New Audit</Link>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={s.centerPage}>
        <div style={s.spinner} />
        <div style={{ color: C.muted, marginTop: "1rem", fontFamily: "'DM Sans', sans-serif" }}>
          Loading report…
        </div>
      </div>
    );
  }

  const { audit, scores, findings, asinCount, reviewCount, brandData, asins = [] } = data;
  const storeJson = brandData?.brandStoreJson ?? null;

  const bySection = scores.reduce<Record<string, typeof scores>>((acc, sc) => {
    if (sc.section === OTHERS_SECTION) return acc;
    (acc[sc.section] ??= []).push(sc);
    return acc;
  }, {});
  const scoredSections = Object.keys(bySection);

  const narrative    = findings.find((f) => f.source === "llm" && f.section === "_narrative");
  const strengths    = findings.filter((f) => f.type === "strength"       && f.section !== OTHERS_SECTION);
  const weaknesses   = findings.filter((f) => f.type === "weakness"       && f.section !== OTHERS_SECTION);
  const watchClosely = weaknesses.filter((f) => f.priority <= 2);
  const recommendations = findings.filter(
    (f) => f.type === "recommendation" && f.section !== "_narrative" && f.section !== OTHERS_SECTION,
  );
  const quickWins = findings.filter((f) => f.type === "quick_win");

  const pdfReady = !!audit.reportPdfGcsPath;
  // Score is always out of 100 by rubric design — never use scorePossible from DB
  // as it may reflect older rubric versions where fewer criteria were marked N/A.
  const scorePct = audit.scoreTotal != null ? Number(audit.scoreTotal) : null;

  const TABS: { id: TabId; label: string }[] = [
    { id: "overview",        label: "1. Overview" },
    { id: "findings",        label: "2. Findings" },
    { id: "recommendations", label: "3. Recommendations" },
    { id: "scores",          label: "4. Detailed Scores" },
    { id: "asins",           label: `5. ASINs (${asinCount})` },
  ];

  return (
    <div style={s.page}>

      {/* Top bar */}
      <div style={s.topBar}>
        <Link to="/" style={s.backLink}>← New Audit</Link>
        <div style={s.topActions}>
          <Link to={`/audits/${id}/override`} style={s.secondaryBtn}>Manual Override</Link>
          <button
            onClick={handleDownloadPdf}
            style={pdfReady ? s.primaryBtn : s.disabledBtn}
            disabled={!pdfReady || downloading}
          >
            {downloading ? "Downloading…" : pdfReady ? "⬇ Download PDF" : "PDF not ready"}
          </button>
        </div>
      </div>

      {/* Hero */}
      <div style={s.hero}>
        <div style={s.heroLabel}>Amazon Brand Audit</div>
        <h1 style={s.brandName}>{audit.brandName}</h1>
        <p style={s.heroDate}>
          {new Date(audit.startedAt).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
        </p>
        <div style={s.heroScoreRow}>
          <div style={{ ...s.gradeCircle, background: gradeAccent(audit.grade) + "22", border: `2px solid ${gradeAccent(audit.grade)}55` }}>
            <div style={{ ...s.gradeLetter, color: gradeAccent(audit.grade) }}>
              {scorePct !== null ? Math.round(scorePct) : "—"}
            </div>
            <div style={s.gradePct}>/100</div>
          </div>
          {audit.grade && GRADE_CONFIG[audit.grade] && (
            <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
              <div style={{
                background: `${gradeAccent(audit.grade)}22`,
                border: `1px solid ${gradeAccent(audit.grade)}55`,
                borderRadius: "20px", padding: "4px 14px",
                fontSize: "0.85rem", fontWeight: 700, color: gradeAccent(audit.grade),
                marginBottom: "4px",
              }}>
                {GRADE_CONFIG[audit.grade].label}
              </div>
              <div style={{ fontSize: "0.72rem", color: C.muted }}>{GRADE_CONFIG[audit.grade].sub}</div>
            </div>
          )}
        </div>

        {/* Product image strip */}
        {asins.filter(a => a.main_image_url).length > 0 && (
          <div style={s.imageStrip}>
            {asins.filter(a => a.main_image_url).slice(0, 6).map((a, i) => (
              <div key={i} style={s.imageStripTile}>
                <img
                  src={a.main_image_url!}
                  alt={a.title || a.asin}
                  style={{ width: "100%", height: "100%", objectFit: "contain", padding: "6px" }}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sticky section nav */}
      <div style={s.stickyNav} ref={navRef}>
        <div style={s.navInner}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{ ...s.navBtn, ...(activeTab === tab.id ? s.navBtnActive : {}) }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab: Overview ── */}
      {activeTab === "overview" && (
        <div style={s.tabContent}>

          {/* Key stats — score always first and always out of 100 */}
          <div style={s.statRow}>
            <StatBox value={`${audit.scoreTotal ?? "—"}/100`} label="Total Score" accent />
            <StatBox value={audit.grade ?? "—"}               label="Grade" accent />
            <StatBox value={asinCount}                        label="Listings Analyzed" />
            <StatBox value={reviewCount.toLocaleString()}     label="Reviews Sampled" />
            <StatBox value={storeJson?.page_count ?? (brandData ? "0" : "—")} label="Store Pages" />
            <StatBox value={brandData?.videoCount ?? "—"}     label="Videos Detected" />
          </div>

          {/* Brand Store presence cards */}
          {brandData && (
            <>
              <h2 style={s.sectionHeading}>Brand Presence</h2>
              <div style={s.cardGrid}>
                <div style={{ ...s.infoCard, borderLeft: `3px solid ${storeJson?.exists ? C.success : C.danger}` }}>
                  <div style={s.infoCardTitle}>Brand Store</div>
                  <div style={s.infoCardValue}>{storeJson?.exists ? "Detected" : "Not found"}</div>
                  {brandData.brandStoreUrl && (
                    <a href={brandData.brandStoreUrl} target="_blank" rel="noreferrer" style={s.infoCardLink}>
                      View store →
                    </a>
                  )}
                </div>
                <div style={{ ...s.infoCard, borderLeft: `3px solid ${storeJson?.has_hero ? C.success : C.muted}` }}>
                  <div style={s.infoCardTitle}>Hero Section</div>
                  <div style={s.infoCardValue}>{storeJson?.has_hero ? "Present" : "Not detected"}</div>
                  <div style={s.infoCardSub}>Custom imagery in brand store landing</div>
                </div>
                <div style={{ ...s.infoCard, borderLeft: `3px solid ${brandData.brandStoryDetected ? C.success : C.warning}` }}>
                  <div style={s.infoCardTitle}>Brand Story</div>
                  <div style={s.infoCardValue}>{brandData.brandStoryDetected ? "Present" : "Not found"}</div>
                  <div style={s.infoCardSub}>About Us / Our Story section</div>
                </div>
                <div style={{ ...s.infoCard, borderLeft: `3px solid ${(storeJson?.nav_depth ?? 0) >= 3 ? C.success : C.warning}` }}>
                  <div style={s.infoCardTitle}>Navigation Depth</div>
                  <div style={s.infoCardValue}>{storeJson?.nav_depth ?? 0} items</div>
                  <div style={s.infoCardSub}>Store sub-page navigation</div>
                </div>
                <div style={{ ...s.infoCard, borderLeft: `3px solid ${(storeJson?.product_tile_count ?? 0) > 0 ? C.success : C.muted}` }}>
                  <div style={s.infoCardTitle}>Product Tiles</div>
                  <div style={s.infoCardValue}>{storeJson?.product_tile_count ?? 0}</div>
                  <div style={s.infoCardSub}>Products featured in Brand Store</div>
                </div>
                <div style={{ ...s.infoCard, borderLeft: `3px solid ${(brandData.videoCount ?? 0) > 0 ? C.success : C.muted}` }}>
                  <div style={s.infoCardTitle}>Video Content</div>
                  <div style={s.infoCardValue}>{brandData.videoCount ?? 0} video{brandData.videoCount !== 1 ? "s" : ""}</div>
                  <div style={s.infoCardSub}>Across Brand Store pages</div>
                </div>
              </div>
            </>
          )}

          {/* About Us text */}
          {storeJson?.about_us_text && (
            <>
              <h2 style={s.sectionHeading}>About This Brand</h2>
              <div style={s.card}>
                <div style={s.cardLabel}>From the Brand Store</div>
                <div style={{ color: C.text, fontWeight: 300, lineHeight: 1.75, fontSize: "0.9rem" }}>
                  {storeJson.about_us_text}
                </div>
              </div>
            </>
          )}

          {/* Executive summary */}
          {narrative && (
            <>
              <h2 style={s.sectionHeading}>Executive Summary</h2>
              <div style={s.card}>
                <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.75, color: C.text, fontWeight: 300 }}>
                  {narrative.text}
                </div>
              </div>
            </>
          )}
          {!narrative && !brandData && (
            <Alert type="info">No brand data collected yet — run the audit to populate this section.</Alert>
          )}

          {/* At-a-glance alerts */}
          {quickWins.length > 0 && (
            <Alert type="success">
              <strong>{quickWins.length} quick win{quickWins.length > 1 ? "s" : ""} identified</strong> — see the Recommendations tab for details.
            </Alert>
          )}
          {weaknesses.length > strengths.length && (
            <Alert type="warn">
              More weaknesses than strengths detected ({weaknesses.length} vs {strengths.length}). Review the Findings tab.
            </Alert>
          )}

          {/* Score by section */}
          <h2 style={s.sectionHeading}>Score by Section</h2>
          <div style={s.scoreSummaryGrid}>
            {scoredSections.map((sec) => {
              const rows    = bySection[sec];
              const earned  = rows.reduce((a, r) => a + Number(r.pointsEarned), 0);
              const possible = rows.reduce((a, r) => a + (r.status !== "na" ? Number(r.pointsPossible) : 0), 0);
              const pct     = possible > 0 ? Math.round((earned / possible) * 100) : 0;
              return (
                <div
                  key={sec}
                  style={s.scoreSummaryCard}
                  onClick={() => { setActiveTab("scores"); toggleSection(sec); }}
                >
                  <div style={s.scoreSummaryName}>{sec}</div>
                  <div style={s.scoreSummaryBar}>
                    <div style={{ ...s.scoreSummaryFill, width: `${pct}%`, background: barColor(pct) }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <ScoreBadge pct={pct} />
                    <span style={{ fontSize: "0.75rem", color: C.muted }}>{earned.toFixed(0)}/{possible.toFixed(0)} pts</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Tab: Findings ── */}
      {activeTab === "findings" && (
        <div style={s.tabContent}>
          <div style={s.findingsGrid3}>
            <div style={{ ...s.findingsColumn, borderTop: `3px solid ${C.success}` }}>
              <div style={{ ...s.columnTitle, color: C.success }}>✦ Strengths</div>
              {strengths.length === 0 ? (
                <div style={s.emptyMsg}>No clear strengths identified.</div>
              ) : (
                strengths.map((f, i) => (
                  <div key={i} style={s.checkItem}>
                    <span style={{ ...s.checkIcon, color: C.success }}>✓</span>
                    <span style={s.checkText}>{f.text}</span>
                  </div>
                ))
              )}
            </div>

            <div style={{ ...s.findingsColumn, borderTop: `3px solid ${C.warning}` }}>
              <div style={{ ...s.columnTitle, color: C.warning }}>⚑ Watch Closely</div>
              {watchClosely.length === 0 ? (
                <div style={s.emptyMsg}>No high-priority issues detected.</div>
              ) : (
                watchClosely.map((f, i) => (
                  <div key={i} style={s.checkItem}>
                    <span style={{ ...s.checkIcon, color: C.warning }}>!</span>
                    <span style={s.checkText}>{f.text}</span>
                  </div>
                ))
              )}
            </div>

            <div style={{ ...s.findingsColumn, borderTop: `3px solid ${C.danger}` }}>
              <div style={{ ...s.columnTitle, color: C.danger }}>Weaknesses</div>
              {weaknesses.length === 0 ? (
                <div style={s.emptyMsg}>No significant weaknesses detected.</div>
              ) : (
                weaknesses.map((f, i) => (
                  <div key={i} style={s.checkItem}>
                    <span style={{ ...s.checkIcon, color: C.danger }}>✕</span>
                    <span style={s.checkText}>{f.text}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {quickWins.length > 0 && (
            <>
              <h2 style={{ ...s.sectionHeading, marginTop: "1.5rem" }}>Quick Wins</h2>
              <div style={s.card}>
                {quickWins.map((f, i) => (
                  <div key={i} style={{ ...s.checkItem, borderBottom: i < quickWins.length - 1 ? `1px solid ${C.border}` : "none" }}>
                    <span style={{ ...s.checkIcon, color: C.warning }}>⚡</span>
                    <span style={s.checkText}>{f.text}</span>
                    {f.section && f.section !== "_narrative" && <Tag color="warn">{f.section}</Tag>}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Tab: Recommendations ── */}
      {activeTab === "recommendations" && (
        <div style={s.tabContent}>
          {recommendations.length === 0 ? (
            <Alert type="info">No recommendations generated yet.</Alert>
          ) : (
            <>
              <Alert type="info">
                {recommendations.length} recommendation{recommendations.length > 1 ? "s" : ""} generated by the scoring engine and LLM enrichment.
              </Alert>
              <div style={s.card}>
                {recommendations.map((r, i) => (
                  <div key={i} style={{ ...s.timelineItem, borderBottom: i < recommendations.length - 1 ? `1px solid ${C.border}` : "none" }}>
                    <div style={s.timelineNum}>{i + 1}</div>
                    <div style={{ flex: 1 }}>
                      <div style={s.timelineText}>{r.text}</div>
                      {r.section && r.section !== "_narrative" && <Tag color="info">{r.section}</Tag>}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {quickWins.length > 0 && (
            <>
              <h2 style={{ ...s.sectionHeading, marginTop: "1.5rem" }}>Quick Wins (High Priority)</h2>
              <div style={s.card}>
                {quickWins.map((f, i) => (
                  <div key={i} style={{ ...s.timelineItem, borderBottom: i < quickWins.length - 1 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ ...s.timelineNum, background: `${C.warning}22`, color: C.warning, border: `1px solid ${C.warning}55` }}>⚡</div>
                    <div style={{ flex: 1 }}>
                      <div style={s.timelineText}>{f.text}</div>
                      {f.section && f.section !== "_narrative" && <Tag color="warn">{f.section}</Tag>}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Tab: Detailed Scores ── */}
      {activeTab === "scores" && (
        <div style={s.tabContent}>
          {scoredSections.map((sec) => {
            const rows    = bySection[sec];
            const earned  = rows.reduce((a, r) => a + Number(r.pointsEarned), 0);
            const possible = rows.reduce((a, r) => a + (r.status !== "na" ? Number(r.pointsPossible) : 0), 0);
            const pct     = possible > 0 ? (earned / possible) * 100 : 0;
            const isOpen  = expandedSections.has(sec);
            return (
              <div key={sec} style={{ ...s.sectionCard, borderLeft: `3px solid ${barColor(pct)}` }}>
                <button onClick={() => toggleSection(sec)} style={s.sectionHeader}>
                  <div style={s.sectionHeaderLeft}>
                    <span style={s.sectionName}>{sec}</span>
                    <ScoreBadge pct={Math.round(pct)} />
                  </div>
                  <div style={s.sectionHeaderRight}>
                    <span style={s.sectionPoints}>{earned.toFixed(1)} / {possible.toFixed(1)} pts</span>
                    <span style={{ color: C.muted, fontSize: "0.8rem" }}>{isOpen ? "▲" : "▼"}</span>
                  </div>
                </button>
                {isOpen && (
                  <div style={s.criteriaTable}>
                    {rows.map((r, i) => (
                      <div key={i} style={s.criteriaRow}>
                        <div style={s.criteriaName}>{r.criterion}</div>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <StatusDot status={r.status} />
                          <span style={s.criteriaScore}>
                            {r.status === "na" ? "N/A" : `${Number(r.pointsEarned).toFixed(1)} / ${Number(r.pointsPossible).toFixed(1)}`}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Tab: ASINs ── */}
      {activeTab === "asins" && (
        <div style={s.tabContent}>
          {asins.length === 0 ? (
            <Alert type="info">No ASIN data captured yet — run the audit to populate this section.</Alert>
          ) : (
            <>
              <Alert type="info">
                {asins.length} ASINs analyzed · Sorted by Best Seller Rank (best first)
              </Alert>
              <div style={s.card}>
                <div style={{ overflowX: "auto" }}>
                  <table style={s.asinTable}>
                    <thead>
                      <tr>
                        <th style={s.th}></th>
                        <th style={s.th}>ASIN</th>
                        <th style={s.th}>Title</th>
                        <th style={s.th}>Rating</th>
                        <th style={s.th}>Reviews</th>
                        <th style={s.th}>BSR</th>
                        <th style={s.th}>Buy Box</th>
                        <th style={s.th}>Images</th>
                        <th style={s.th}>A+</th>
                        <th style={s.th}>Video</th>
                      </tr>
                    </thead>
                    <tbody>
                      {asins.map((a, i) => (
                        <tr key={i} style={{ borderBottom: `1px solid ${C.surface2}` }}>
                          <td style={s.td}>
                            {a.main_image_url ? (
                              <div style={s.asinThumb}>
                                <img src={a.main_image_url} alt="" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                              </div>
                            ) : <div style={s.asinThumb} />}
                          </td>
                          <td style={{ ...s.td, fontFamily: "monospace", fontSize: "0.78rem", color: C.muted, whiteSpace: "nowrap" }}>{a.asin}</td>
                          <td style={{ ...s.td, maxWidth: "220px", fontSize: "0.82rem" }}>
                            <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.title || "—"}</div>
                          </td>
                          <td style={{ ...s.td, textAlign: "center" }}>
                            {a.rating ? <span style={{ color: C.warning, fontWeight: 600 }}>{Number(a.rating).toFixed(1)}★</span> : <span style={{ color: C.muted }}>—</span>}
                          </td>
                          <td style={{ ...s.td, textAlign: "right", fontFamily: "monospace", fontSize: "0.82rem" }}>
                            {a.review_count != null ? a.review_count.toLocaleString() : <span style={{ color: C.muted }}>—</span>}
                          </td>
                          <td style={{ ...s.td, textAlign: "right", fontFamily: "monospace", fontSize: "0.82rem" }}>
                            {a.bsr != null ? `#${a.bsr.toLocaleString()}` : <span style={{ color: C.muted }}>—</span>}
                          </td>
                          <td style={{ ...s.td, fontSize: "0.78rem", maxWidth: "120px" }}>
                            <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: C.muted }}>{a.buybox_seller || "—"}</div>
                          </td>
                          <td style={{ ...s.td, textAlign: "center" }}>{a.image_count}</td>
                          <td style={{ ...s.td, textAlign: "center" }}><Check val={a.has_aplus} /></td>
                          <td style={{ ...s.td, textAlign: "center" }}><Check val={a.has_video} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Footer */}
      <div style={s.footer}>
        <Link to="/" style={s.primaryBtn}>+ Run Another Audit</Link>
        <Link to="/methodology" style={s.secondaryBtn}>Scoring Methodology</Link>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function StatBox({ value, label, accent }: { value: string | number; label: string; accent?: boolean }) {
  return (
    <div style={{ ...s.statBox, ...(accent ? { borderTop: `3px solid ${C.accent}` } : {}) }}>
      <div style={{ ...s.statNum, ...(accent ? { color: C.accent } : {}) }}>{value}</div>
      <div style={s.statLabel}>{label}</div>
    </div>
  );
}

function Alert({ type, children }: { type: "info" | "warn" | "success" | "danger"; children: React.ReactNode }) {
  const cfg = {
    info:    { bg: `${C.info}14`,    border: C.info,    color: C.info },
    warn:    { bg: `${C.warning}14`, border: C.warning, color: C.warning },
    success: { bg: `${C.success}14`, border: C.success, color: C.success },
    danger:  { bg: `${C.danger}14`,  border: C.danger,  color: C.danger },
  }[type];
  return (
    <div style={{ ...s.alert, background: cfg.bg, borderLeft: `3px solid ${cfg.border}`, color: cfg.color }}>
      {children}
    </div>
  );
}

function Tag({ color, children }: { color: "info" | "warn" | "success" | "danger" | "brand"; children: React.ReactNode }) {
  const cfg = {
    brand:   { bg: `${C.accent}26`,   color: C.accent },
    info:    { bg: `${C.info}1F`,     color: C.info },
    warn:    { bg: `${C.warning}1F`,  color: C.warning },
    success: { bg: `${C.success}1F`,  color: C.success },
    danger:  { bg: `${C.danger}1F`,   color: C.danger },
  }[color];
  return (
    <span style={{ ...s.tag, background: cfg.bg, color: cfg.color }}>{children}</span>
  );
}

function ScoreBadge({ pct }: { pct: number }) {
  const color = barColor(pct);
  return (
    <span style={{ ...s.badge, background: `${color}22`, color, border: `1px solid ${color}55` }}>
      {pct}%
    </span>
  );
}

function Check({ val }: { val: boolean }) {
  return val
    ? <span style={{ color: C.success, fontWeight: 700, fontSize: "14px" }}>✓</span>
    : <span style={{ color: C.surface2, fontSize: "14px" }}>—</span>;
}

function StatusDot({ status }: { status: string }) {
  const color = status === "scored" ? C.success : status === "warning" ? C.warning : C.muted;
  return (
    <span style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", background: color, flexShrink: 0 }} />
  );
}

function gradeAccent(grade: string | null): string {
  const cfg = GRADE_CONFIG[grade ?? ""];
  return cfg?.color ?? C.muted;
}

function barColor(pct: number): string {
  return pct >= 80 ? C.success : pct >= 60 ? C.warning : C.danger;
}

// ── Styles ──────────────────────────────────────────────────────────────────
const s: Record<string, React.CSSProperties> = {
  page:      { maxWidth: "960px", margin: "0 auto", padding: "0 1rem 5rem" },
  centerPage: { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh" },

  // Top bar
  topBar: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "1rem 0", borderBottom: `1px solid ${C.border}`, marginBottom: "1.5rem",
  },
  backLink:   { color: C.muted, textDecoration: "none", fontSize: "0.9rem", fontWeight: 500 },
  topActions: { display: "flex", gap: "0.5rem", alignItems: "center" },

  // Hero
  hero: {
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: "12px",
    padding: "2rem 2rem 1.5rem", marginBottom: 0,
  },
  heroLabel: {
    textTransform: "uppercase", letterSpacing: "3px", fontSize: "11px",
    color: C.accent, fontWeight: 500, marginBottom: "0.5rem",
  },
  brandName: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: "2.4rem", color: C.accent, margin: "0 0 0.2rem", lineHeight: 1.2,
  },
  heroDate: { color: C.muted, fontSize: "0.88rem", margin: "0 0 1rem", fontWeight: 300 },
  heroScoreRow: { display: "flex", alignItems: "center", gap: "1.5rem" },
  heroScoreStat: { display: "flex", flexDirection: "column" as const },
  heroScoreNum:  { fontSize: "1.6rem", fontWeight: 700, color: C.accentLight, fontFamily: "'DM Serif Display', Georgia, serif" },
  heroScoreLabel: { fontSize: "0.7rem", color: C.muted, textTransform: "uppercase" as const, letterSpacing: "0.08em", marginTop: "2px" },
  gradeCircle: {
    width: "72px", height: "72px", borderRadius: "50%",
    display: "flex", flexDirection: "column" as const, alignItems: "center", justifyContent: "center",
    flexShrink: 0,
  },
  gradeLetter: { fontSize: "2rem", fontWeight: 800, fontFamily: "'DM Serif Display', Georgia, serif", lineHeight: 1 },
  gradePct:    { fontSize: "0.72rem", color: C.muted, marginTop: "1px" },

  // Card grid (brand presence)
  cardGrid: {
    display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    gap: "12px", marginBottom: "1.5rem",
  },
  infoCard: {
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: "10px",
    padding: "16px 18px",
  },
  infoCardTitle: {
    fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
    letterSpacing: "0.08em", color: C.muted, marginBottom: "6px",
  },
  infoCardValue: {
    fontSize: "1.1rem", fontWeight: 600, color: C.text, marginBottom: "4px",
    fontFamily: "'DM Serif Display', Georgia, serif",
  },
  infoCardSub:  { fontSize: "0.78rem", color: C.muted, fontWeight: 300 },
  infoCardLink: { fontSize: "0.78rem", color: C.accent, textDecoration: "none", display: "block", marginTop: "4px" },

  // Stat row
  statRow: { display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "12px", marginBottom: "1.5rem" },
  statBox: {
    background: C.bg, border: `1px solid ${C.border}`, borderRadius: "8px",
    padding: "14px 16px", textAlign: "center",
  },
  statNum:   { fontSize: "1.8rem", fontFamily: "'DM Serif Display', Georgia, serif", color: C.accent },
  statLabel: { fontSize: "0.72rem", color: C.muted, marginTop: "3px", letterSpacing: "0.03em" },

  // Sticky nav
  stickyNav: {
    position: "sticky", top: 0, zIndex: 50,
    background: `${C.bg}F2`, backdropFilter: "blur(20px)",
    borderBottom: `1px solid ${C.border}`, marginBottom: 0,
  },
  navInner: {
    display: "flex", gap: "6px", padding: "10px 0",
    overflowX: "auto",
  },
  navBtn: {
    whiteSpace: "nowrap" as const, padding: "7px 16px",
    border: `1px solid ${C.border}`, borderRadius: "20px",
    background: "transparent", color: C.muted,
    fontSize: "13px", cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
    transition: "all 0.2s",
  },
  navBtnActive: {
    background: C.accent, color: C.bg, borderColor: C.accent, fontWeight: 600,
  },

  // Tab content
  tabContent: { paddingTop: "1.5rem", animation: "fadeIn 0.4s ease" },

  // Cards
  card: {
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: "10px",
    padding: "1.25rem 1.5rem", marginBottom: "1rem",
  },
  cardLabel: {
    fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
    letterSpacing: "0.1em", color: C.muted, marginBottom: "0.75rem",
  },

  // Section headings
  sectionHeading: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: "1.5rem", color: C.accentLight,
    margin: "2rem 0 1rem", lineHeight: 1.3,
  },

  // Score summary grid (overview)
  scoreSummaryGrid: {
    display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(270px, 1fr))",
    gap: "12px", marginBottom: "1.5rem",
  },
  scoreSummaryCard: {
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: "8px",
    padding: "14px 16px", cursor: "pointer",
  },
  scoreSummaryName: { fontSize: "0.85rem", fontWeight: 600, color: C.text, marginBottom: "8px" },
  scoreSummaryBar:  { height: "4px", background: C.surface2, borderRadius: "2px", marginBottom: "8px", overflow: "hidden" },
  scoreSummaryFill: { height: "100%", borderRadius: "2px" },

  // Findings
  findingsGrid:  { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" },
  findingsGrid3: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" },
  findingsColumn: {
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: "10px",
    padding: "1.25rem",
  },
  columnTitle: {
    fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase",
    letterSpacing: "0.06em", marginBottom: "1rem",
  },

  // Checklist
  checkItem: {
    display: "flex", alignItems: "flex-start", gap: "10px",
    padding: "8px 0", fontSize: "0.875rem",
  },
  checkIcon: { fontSize: "14px", flexShrink: 0, marginTop: "1px", fontWeight: 700 },
  checkText: { color: C.text, lineHeight: 1.55, flex: 1, fontWeight: 300 },

  // Timeline
  timelineItem: {
    display: "flex", alignItems: "flex-start", gap: "12px",
    padding: "12px 0",
  },
  timelineNum: {
    width: "26px", height: "26px", borderRadius: "50%", flexShrink: 0,
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: "0.72rem", fontWeight: 700,
    background: `${C.info}1F`, color: C.info, border: `1px solid ${C.info}4D`,
  },
  timelineText: { fontSize: "0.9rem", color: C.text, lineHeight: 1.55, marginBottom: "4px", fontWeight: 300 },

  // Alert
  alert: {
    padding: "12px 16px", borderRadius: "8px", marginBottom: "1rem",
    fontSize: "0.875rem", lineHeight: 1.55, fontWeight: 400,
  },

  // Tag
  tag: {
    display: "inline-block", padding: "3px 10px", borderRadius: "20px",
    fontSize: "11px", fontWeight: 500, marginTop: "4px", margin: "3px",
  },

  // Section score cards
  sectionCard: {
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: "8px",
    marginBottom: "0.5rem", overflow: "hidden",
  },
  sectionHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    width: "100%", background: "transparent", border: "none", cursor: "pointer",
    padding: "0.9rem 1.25rem", textAlign: "left" as const,
  },
  sectionHeaderLeft:  { display: "flex", alignItems: "center", gap: "0.75rem" },
  sectionHeaderRight: { display: "flex", alignItems: "center", gap: "1rem" },
  sectionName:   { fontSize: "0.95rem", fontWeight: 600, color: C.text },
  sectionPoints: { fontFamily: "'SF Mono', Consolas, monospace", fontSize: "0.82rem", color: C.muted },
  badge: {
    padding: "2px 8px", borderRadius: "10px", fontSize: "0.72rem",
    fontWeight: 700, letterSpacing: "0.03em",
  },
  criteriaTable: { borderTop: `1px solid ${C.border}` },
  criteriaRow: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "0.6rem 1.25rem", borderBottom: `1px solid ${C.surface2}`,
  },
  criteriaName:  { fontSize: "0.85rem", color: C.text, flex: 1, fontWeight: 300 },
  criteriaScore: { fontSize: "0.8rem", color: C.muted, fontFamily: "'SF Mono', Consolas, monospace" },

  // Buttons
  primaryBtn: {
    padding: "0.65rem 1.4rem", background: C.accent, color: C.bg,
    border: "none", borderRadius: "24px", cursor: "pointer", fontWeight: 600,
    fontSize: "0.95rem", textDecoration: "none", display: "inline-block",
    fontFamily: "'DM Sans', sans-serif",
  },
  secondaryBtn: {
    padding: "0.65rem 1.2rem", background: "transparent", color: C.text,
    border: `1px solid ${C.border}`, borderRadius: "24px", cursor: "pointer",
    fontWeight: 500, fontSize: "0.9rem", textDecoration: "none", display: "inline-block",
    fontFamily: "'DM Sans', sans-serif",
  },
  disabledBtn: {
    padding: "0.65rem 1.4rem", background: C.surface2, color: C.muted,
    border: `1px solid ${C.border}`, borderRadius: "24px", cursor: "not-allowed",
    fontWeight: 600, fontSize: "0.95rem",
  },
  linkBtn: {
    padding: "0.5rem 1rem", background: C.surface2, color: C.text,
    borderRadius: "6px", textDecoration: "none", fontSize: "0.9rem",
  },

  // Product image strip (hero)
  imageStrip: {
    display: "flex", gap: "8px", marginTop: "1.25rem",
    overflowX: "auto", paddingBottom: "4px",
  },
  imageStripTile: {
    width: "72px", height: "72px", flexShrink: 0,
    background: C.surface2, border: `1px solid ${C.border}`,
    borderRadius: "8px", overflow: "hidden",
  },

  // ASIN table
  asinTable: {
    width: "100%", borderCollapse: "collapse" as const,
    fontSize: "0.83rem",
  },
  th: {
    padding: "8px 10px", textAlign: "left" as const,
    fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase" as const,
    letterSpacing: "0.06em", color: C.muted,
    borderBottom: `1px solid ${C.border}`,
    whiteSpace: "nowrap" as const,
  },
  td: {
    padding: "8px 10px", color: C.text,
    verticalAlign: "middle" as const,
  },
  asinThumb: {
    width: "40px", height: "40px",
    background: C.surface2, borderRadius: "6px",
    overflow: "hidden", flexShrink: 0,
  },

  // Footer / misc
  footer: { display: "flex", gap: "0.75rem", marginTop: "3rem", justifyContent: "center" },
  errorCard: {
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: "8px",
    padding: "2rem", textAlign: "center" as const,
  },
  spinner: {
    width: "32px", height: "32px", border: `3px solid ${C.border}`,
    borderTop: `3px solid ${C.accent}`, borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  emptyMsg: { fontSize: "0.85rem", color: C.muted, fontStyle: "italic" },
};
