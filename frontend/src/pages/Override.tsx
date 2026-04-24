import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getAudit, submitOverrides, type AuditDetailResponse } from "../lib/api";

interface EditableRow {
  section: string;
  criterion: string;
  fieldPath: string;
  currentValue: string;
  overrideValue: string;
  status: string;
}

export function Override() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<AuditDetailResponse | null>(null);
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getAudit(id)
      .then((d) => {
        setData(d);
        setRows(
          d.scores.map((s) => {
            const currentValue = s.evidence ? JSON.stringify(s.evidence) : "";
            return {
              section: s.section,
              criterion: s.criterion,
              fieldPath: `scores.${s.section}.${s.criterion}`,
              currentValue,
              overrideValue: "",
              status: s.status,
            };
          }),
        );
      })
      .catch((err) => setError((err as Error).message));
  }, [id]);

  const dirty = useMemo(() => rows.filter((r) => r.overrideValue.trim() !== ""), [rows]);

  async function save() {
    if (!id || dirty.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload = dirty.map((r) => {
        let parsed: unknown = r.overrideValue;
        try {
          parsed = JSON.parse(r.overrideValue);
        } catch {
          /* keep as string */
        }
        return {
          fieldPath: r.fieldPath,
          originalValue: safeJson(r.currentValue),
          overrideValue: parsed,
        };
      });
      await submitOverrides(id, payload);
      // Redirect to Progress screen so the user sees the rescore run.
      navigate(`/audits/${id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  if (error) return <div style={{ color: "var(--color-danger)" }}>Error: {error}</div>;
  if (!data) return <div>Loading overrides…</div>;

  return (
    <section>
      <h1>Manual Override — {data.audit.brandName}</h1>
      <p style={{ color: "var(--color-text-muted)" }}>
        Correct any scraped value that looks wrong. The{" "}
        <strong>override value</strong> column accepts raw text or JSON (e.g.{" "}
        <code>{`{"ratio": 0.85}`}</code>). When you Save, the audit version bumps and
        the scoring engine re-runs using your corrections.
      </p>

      <div style={{ display: "flex", gap: "0.5rem", margin: "1rem 0" }}>
        <button
          onClick={save}
          disabled={submitting || dirty.length === 0}
          style={{
            padding: "0.6rem 1.2rem",
            background:
              dirty.length > 0 ? "var(--color-accent)" : "var(--color-border)",
            color: "white",
            border: "none",
            borderRadius: "6px",
            cursor: dirty.length > 0 ? "pointer" : "default",
            fontWeight: 600,
          }}
        >
          {submitting
            ? "Saving…"
            : dirty.length === 0
            ? "No changes"
            : `Save & Re-score (${dirty.length})`}
        </button>
        <Link
          to={`/audits/${id}/report`}
          style={{
            padding: "0.6rem 1.2rem",
            background: "var(--color-surface)",
            color: "var(--color-text)",
            border: "1px solid var(--color-border)",
            borderRadius: "6px",
            textDecoration: "none",
          }}
        >
          Cancel
        </Link>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Section</th>
            <th style={{ textAlign: "left" }}>Criterion</th>
            <th style={{ textAlign: "left" }}>Current Evidence</th>
            <th style={{ textAlign: "left" }}>Override (raw or JSON)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderBottom: "1px solid var(--color-border)" }}>
              <td style={{ padding: "0.4rem 0.6rem", color: "var(--color-text-muted)" }}>
                {r.section}
              </td>
              <td style={{ padding: "0.4rem 0.6rem" }}>
                {r.criterion}
                <div
                  style={{
                    fontSize: "0.7rem",
                    color: "var(--color-text-muted)",
                    marginTop: "0.1rem",
                  }}
                >
                  {r.status}
                </div>
              </td>
              <td
                style={{
                  padding: "0.4rem 0.6rem",
                  fontFamily: "SF Mono, monospace",
                  fontSize: "0.75rem",
                  color: "var(--color-text-muted)",
                  maxWidth: "260px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={r.currentValue}
              >
                {r.currentValue}
              </td>
              <td style={{ padding: "0.4rem 0.6rem" }}>
                <input
                  type="text"
                  value={r.overrideValue}
                  onChange={(e) => {
                    const v = e.target.value;
                    setRows((prev) =>
                      prev.map((row, idx) =>
                        idx === i ? { ...row, overrideValue: v } : row,
                      ),
                    );
                  }}
                  placeholder="(leave blank to keep current)"
                  style={{
                    width: "100%",
                    padding: "0.3rem 0.5rem",
                    background: "var(--color-bg)",
                    color: "var(--color-text)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "4px",
                    fontFamily: "SF Mono, monospace",
                    fontSize: "0.8rem",
                  }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function safeJson(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return s;
  }
}
