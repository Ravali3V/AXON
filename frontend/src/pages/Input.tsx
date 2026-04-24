import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createAudit, listAudits } from "../lib/api";

const GRADE_COLORS: Record<string, string> = {
  Thriving: "#27AE60",
  Growing:  "#E8622A",
  Building: "#3498DB",
  Emerging: "#E67E22",
  Untapped: "#E74C3C",
};

interface RecentRow {
  id: string;
  brandName: string;
  status: string;
  grade: string | null;
  scoreTotal: number | null;
  scorePossible: number | null;
  startedAt: string;
}

export function Input() {
  const navigate = useNavigate();
  const [brand, setBrand] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<RecentRow[]>([]);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    try {
      const audits = await listAudits();
      setRecent(
        audits.map((a) => ({
          id: (a as unknown as { id: string }).id,
          brandName: a.brandName,
          status: a.status,
          grade: a.grade,
          scoreTotal: a.scoreTotal,
          scorePossible: a.scorePossible,
          startedAt: a.startedAt,
        })),
      );
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("failed to load recent audits", err);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!brand.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const { auditId } = await createAudit({ brandName: brand.trim() });
      navigate(`/audits/${auditId}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h1>Run a Tier 1 Brand Audit</h1>
      <p style={{ color: "var(--color-text-muted)" }}>
        Enter an Amazon brand name. AXON will crawl their public catalog, Brand Store,
        and reviews, score them against the 100-point rubric, and generate a branded
        PDF report.
      </p>

      <form onSubmit={onSubmit} style={styles.form}>
        <input
          type="text"
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
          placeholder="Brand name (e.g. Anker, Logitech G)"
          style={styles.input}
          disabled={busy}
          autoFocus
        />
        <button type="submit" disabled={busy || !brand.trim()} style={styles.button}>
          {busy ? "Queuing…" : "Start audit"}
        </button>
      </form>

      {error && <div style={styles.error}>Error: {error}</div>}

      <h2 style={{ marginTop: "2rem" }}>Recent audits</h2>
      {recent.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)" }}>No audits yet.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th>Brand</th>
              <th>Status</th>
              <th>Grade</th>
              <th>Score</th>
              <th>Started</th>
              <th>&nbsp;</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((a) => (
              <tr key={a.id}>
                <td>{a.brandName}</td>
                <td>
                  <span style={statusStyle(a.status)}>{a.status}</span>
                </td>
                <td>
                  {a.grade && GRADE_COLORS[a.grade] ? (
                    <span style={gradeBadgeStyle(a.grade)}>{a.grade}</span>
                  ) : (a.grade ?? "—")}
                </td>
                <td>
                  {a.scoreTotal !== null && a.scorePossible !== null
                    ? `${a.scoreTotal}/${a.scorePossible}`
                    : "—"}
                </td>
                <td>{new Date(a.startedAt).toLocaleString()}</td>
                <td>
                  <a href={`/audits/${a.id}`} style={styles.link}>
                    View
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  form: {
    display: "flex",
    gap: "0.5rem",
    marginTop: "1.5rem",
    marginBottom: "0.5rem",
  },
  input: {
    flex: 1,
    padding: "0.6rem 0.8rem",
    fontSize: "1rem",
    background: "var(--color-surface)",
    color: "var(--color-text)",
    border: "1px solid var(--color-border)",
    borderRadius: "6px",
  },
  button: {
    padding: "0.6rem 1.2rem",
    fontSize: "1rem",
    background: "var(--color-accent)",
    color: "white",
    border: "none",
    borderRadius: "6px",
    cursor: "pointer",
    fontWeight: 600,
  },
  error: {
    marginTop: "0.5rem",
    color: "var(--color-danger)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    marginTop: "0.5rem",
  },
  link: {
    color: "var(--color-accent)",
    textDecoration: "none",
  },
};

function gradeBadgeStyle(grade: string): React.CSSProperties {
  const color = GRADE_COLORS[grade] ?? "#9B9A97";
  return {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: "12px",
    fontSize: "0.75rem",
    fontWeight: 700,
    background: `${color}22`,
    border: `1px solid ${color}55`,
    color,
  };
}

function statusStyle(status: string): React.CSSProperties {
  const colors: Record<string, string> = {
    complete: "var(--color-success)",
    failed: "var(--color-danger)",
    queued: "var(--color-text-muted)",
  };
  return {
    color: colors[status] ?? "var(--color-warning)",
    fontWeight: 600,
    textTransform: "uppercase",
    fontSize: "0.8rem",
    letterSpacing: "0.03em",
  };
}
