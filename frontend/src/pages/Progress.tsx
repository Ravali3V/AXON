import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getAudit, openEventStream, type ProgressEvent } from "../lib/api";

const STAGE_META: Array<{ key: string; label: string; icon: string }> = [
  { key: "queued",             label: "Queued",          icon: "○" },
  { key: "resolve_brand",      label: "Brand Lookup",    icon: "🔍" },
  { key: "discover_asins",     label: "Discover ASINs",  icon: "📦" },
  { key: "scrape_pdp",         label: "Scrape Listings", icon: "🔗" },
  { key: "scrape_brand_store", label: "Brand Store",     icon: "🏪" },
  { key: "scrape_reviews",     label: "Reviews",         icon: "⭐" },
  { key: "scoring",            label: "Scoring",         icon: "📊" },
  { key: "enrich",             label: "AI Analysis",     icon: "🤖" },
  { key: "render_pdf",         label: "PDF Report",      icon: "📄" },
  { key: "complete",           label: "Complete",        icon: "✅" },
];

const STAGE_KEYS = STAGE_META.map((s) => s.key);

function dedupEvents(events: ProgressEvent[]): ProgressEvent[] {
  const seen = new Set<string>();
  return events.filter((ev) => {
    const key = `${ev.ts}|${ev.stage}|${ev.message}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function Progress() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [status, setStatus] = useState<string>("queued");
  const [brandName, setBrandName] = useState<string>("");
  const [connError, setConnError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    getAudit(id)
      .then((data) => {
        setStatus(data.audit.status);
        setBrandName(data.audit.brandName);
        if (data.audit.status === "complete") {
          navigate(`/audits/${id}/report`, { replace: true });
        }
      })
      .catch((err) => setConnError((err as Error).message));

    const close = openEventStream(
      id,
      (ev) => {
        setEvents((prev) => dedupEvents([...prev, ev]));
        setStatus(ev.status);
        if (ev.status === "complete") {
          setTimeout(() => navigate(`/audits/${id}/report`), 900);
        }
      },
      () => setConnError("Connection lost — retrying…"),
    );
    return close;
  }, [id, navigate]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  const currentStageIdx = STAGE_KEYS.findIndex((s) => s === status);
  const activeStages = new Set(events.map((e) => e.stage));

  const asinCount = (() => {
    const match = events
      .filter((e) => e.stage === "discover_asins")
      .map((e) => e.message.match(/total\s+(\d+)/i)?.[1] ?? e.message.match(/(\d+)\s+ASINs/i)?.[1])
      .filter(Boolean)
      .pop();
    return match ? parseInt(match as string, 10) : null;
  })();

  const pdpProgress = (() => {
    const last = events.filter((e) => e.stage === "scrape_pdp" && e.message.includes("PDP progress")).pop();
    return last?.message.match(/(\d+)\/(\d+)/)?.[0] ?? null;
  })();

  const isFailed = status === "failed";

  return (
    <div style={s.page}>
      <div style={s.topBar}>
        <Link to="/" style={s.backLink}>← New Audit</Link>
        <div style={s.topBarCenter}>
          {brandName && <span style={s.topBrand}>{brandName}</span>}
          <span style={isFailed ? s.badgeFailed : s.badgeRunning}>
            {isFailed ? "Failed" : status === "complete" ? "Complete" : "Running…"}
          </span>
        </div>
      </div>

      {/* Stage pipeline */}
      <div style={s.pipeline}>
        {STAGE_META.map((stage, i) => {
          const isDone = i < currentStageIdx || status === "complete";
          const isActive = i === currentStageIdx && status !== "complete";
          const isFut = !isDone && !isActive;
          return (
            <div key={stage.key} style={s.stageItem}>
              {i > 0 && (
                <div
                  style={{
                    ...s.connector,
                    background: isDone ? "#3fb950" : "#30363d",
                  }}
                />
              )}
              <div
                style={{
                  ...s.stageCircle,
                  background: isDone
                    ? "#3fb950"
                    : isActive
                    ? "#2f81f7"
                    : "#21262d",
                  border: isActive
                    ? "2px solid #58a6ff"
                    : isDone
                    ? "2px solid #3fb950"
                    : "2px solid #30363d",
                  boxShadow: isActive ? "0 0 0 3px rgba(47,129,247,0.25)" : undefined,
                }}
              >
                <span style={{ fontSize: isFut ? "0.85rem" : "1rem" }}>
                  {isDone ? "✓" : stage.icon}
                </span>
              </div>
              <div
                style={{
                  ...s.stageLabel,
                  color: isDone
                    ? "#3fb950"
                    : isActive
                    ? "#58a6ff"
                    : "#7d8590",
                  fontWeight: isActive ? 700 : 500,
                }}
              >
                {stage.label}
              </div>
            </div>
          );
        })}
      </div>

      {/* Stats row */}
      {(asinCount !== null || pdpProgress) && (
        <div style={s.statsRow}>
          {asinCount !== null && (
            <div style={s.statCard}>
              <div style={s.statValue}>{asinCount}</div>
              <div style={s.statLabel}>ASINs Discovered</div>
            </div>
          )}
          {pdpProgress && (
            <div style={s.statCard}>
              <div style={s.statValue}>{pdpProgress}</div>
              <div style={s.statLabel}>Listings Scraped</div>
            </div>
          )}
        </div>
      )}

      {connError && (
        <div style={s.errorBanner}>{connError}</div>
      )}

      {/* Event log */}
      <div style={s.logHeader}>
        <span style={s.logTitle}>Live Log</span>
        <span style={s.logCount}>{events.length} events</span>
      </div>
      <div ref={logRef} style={s.log}>
        {events.length === 0 ? (
          <div style={{ color: "#7d8590", padding: "0.5rem 0" }}>
            Waiting for first event…
          </div>
        ) : (
          events.map((ev, i) => (
            <div key={i} style={s.logLine}>
              <span style={s.logTs}>
                {new Date(ev.ts).toLocaleTimeString()}
              </span>
              <span style={logLevelStyle(ev.level)}>{ev.level.toUpperCase()}</span>
              <span style={s.logStage}>[{ev.stage}]</span>
              <span style={{ color: "#c9d1d9" }}>{ev.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function logLevelStyle(level: string): React.CSSProperties {
  const colors: Record<string, string> = {
    info: "#3fb950",
    warn: "#d29922",
    error: "#f85149",
  };
  return {
    color: colors[level] ?? "#7d8590",
    fontWeight: 700,
    minWidth: "48px",
    display: "inline-block",
  };
}

const s: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: "1000px",
    margin: "0 auto",
    padding: "0 1rem 3rem",
  },
  topBar: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    padding: "1rem 0",
    marginBottom: "1.5rem",
    borderBottom: "1px solid #21262d",
  },
  backLink: {
    color: "#7d8590",
    textDecoration: "none",
    fontSize: "0.9rem",
    fontWeight: 500,
    whiteSpace: "nowrap",
  },
  topBarCenter: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    flex: 1,
  },
  topBrand: {
    fontSize: "1.1rem",
    fontWeight: 700,
    color: "#e6edf3",
  },
  badgeRunning: {
    padding: "2px 10px",
    borderRadius: "12px",
    fontSize: "0.75rem",
    fontWeight: 700,
    background: "#1f4a8c",
    color: "#58a6ff",
    border: "1px solid #2f81f7",
  },
  badgeFailed: {
    padding: "2px 10px",
    borderRadius: "12px",
    fontSize: "0.75rem",
    fontWeight: 700,
    background: "#3d1c1c",
    color: "#f85149",
    border: "1px solid #f85149",
  },
  pipeline: {
    display: "flex",
    alignItems: "flex-start",
    overflowX: "auto",
    padding: "1rem 0 1.5rem",
    gap: 0,
    marginBottom: "1.5rem",
  },
  stageItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    position: "relative",
    flex: 1,
    minWidth: "72px",
  },
  connector: {
    position: "absolute",
    top: "20px",
    left: "-50%",
    width: "100%",
    height: "2px",
    zIndex: 0,
  },
  stageCircle: {
    width: "40px",
    height: "40px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
    position: "relative",
    transition: "background 0.3s, border-color 0.3s",
    cursor: "default",
  },
  stageLabel: {
    marginTop: "0.4rem",
    fontSize: "0.65rem",
    fontWeight: 500,
    textAlign: "center",
    letterSpacing: "0.02em",
    lineHeight: 1.3,
    maxWidth: "72px",
    wordBreak: "break-word",
  },
  statsRow: {
    display: "flex",
    gap: "1rem",
    marginBottom: "1.5rem",
  },
  statCard: {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: "8px",
    padding: "0.75rem 1.25rem",
    minWidth: "120px",
    textAlign: "center",
  },
  statValue: {
    fontSize: "1.75rem",
    fontWeight: 700,
    color: "#58a6ff",
    lineHeight: 1,
  },
  statLabel: {
    fontSize: "0.75rem",
    color: "#7d8590",
    marginTop: "0.25rem",
  },
  errorBanner: {
    background: "#3d1c1c",
    border: "1px solid #f85149",
    borderRadius: "6px",
    padding: "0.6rem 1rem",
    color: "#f85149",
    fontSize: "0.9rem",
    marginBottom: "1rem",
  },
  logHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "0.4rem",
  },
  logTitle: {
    fontSize: "0.85rem",
    fontWeight: 700,
    color: "#7d8590",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  logCount: {
    fontSize: "0.75rem",
    color: "#7d8590",
  },
  log: {
    background: "#010409",
    color: "#c9d1d9",
    padding: "0.75rem 1rem",
    borderRadius: "6px",
    height: "45vh",
    overflowY: "auto",
    fontFamily: "'SF Mono', Consolas, Menlo, monospace",
    fontSize: "0.8rem",
    border: "1px solid #21262d",
  },
  logLine: {
    display: "grid",
    gridTemplateColumns: "80px 52px 170px 1fr",
    gap: "0.5rem",
    padding: "0.18rem 0",
    borderBottom: "1px solid #0d1117",
    alignItems: "start",
  },
  logTs: { color: "#7d8590" },
  logStage: { color: "#2f81f7" },
};
