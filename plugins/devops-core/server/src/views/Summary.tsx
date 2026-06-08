import React from "react";
import type { ClusterContext, ResultRow, DeferredMajor } from "../types";

interface SummaryData {
  action: "summary";
  cluster: ClusterContext;
  results: ResultRow[];
  deferred_majors: DeferredMajor[];
}

interface SummaryViewProps {
  data: SummaryData;
}

function resultPill(status: string) {
  const s = status?.toLowerCase();
  if (s === "updated") return <span className="status-pill status-ok">✅ updated</span>;
  if (s === "skipped") return <span className="status-pill status-skip">⏭ skipped</span>;
  if (s === "deferred") return <span className="status-pill status-warn">🔍 deferred</span>;
  if (s === "blocked") return <span className="status-pill status-block">🔴 blocked</span>;
  return <span className="status-pill status-skip">{status}</span>;
}

export function SummaryView({ data }: SummaryViewProps) {
  const { cluster, results, deferred_majors: deferred } = data;

  const counts = { updated: 0, skipped: 0, deferred: 0, blocked: 0 };
  for (const r of results) {
    const s = r.status?.toLowerCase() as keyof typeof counts;
    if (s in counts) counts[s]++;
  }

  return (
    <div className="view">
      <div className="view-header">
        <h1>Upgrade Summary</h1>
      </div>

      {/* Cluster bar */}
      <div className="cluster-bar">
        <span className="badge">
          <strong>Cluster</strong> {cluster.name}
        </span>
        <span className="badge">
          <strong>Region</strong> {cluster.region}
        </span>
        {cluster.profile && (
          <span className="badge">
            <strong>Profile</strong> {cluster.profile}
          </span>
        )}
        {cluster.k8s_version && (
          <span className="badge">
            <strong>K8s</strong> {cluster.k8s_version}
          </span>
        )}
      </div>

      {/* Stat cards */}
      <div className="stat-cards">
        <div className="stat-card stat-updated">
          <div className="stat-value">{counts.updated}</div>
          <div className="stat-label">Updated</div>
        </div>
        <div className="stat-card stat-skipped">
          <div className="stat-value">{counts.skipped}</div>
          <div className="stat-label">Skipped</div>
        </div>
        <div className="stat-card stat-deferred">
          <div className="stat-value">{counts.deferred}</div>
          <div className="stat-label">Deferred</div>
        </div>
        <div className="stat-card stat-blocked">
          <div className="stat-value">{counts.blocked}</div>
          <div className="stat-label">Blocked</div>
        </div>
      </div>

      {/* Results table */}
      <div className="section-title">Results</div>
      {results.length === 0 ? (
        <p className="empty">No results recorded.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Package</th>
                <th>Source</th>
                <th>From</th>
                <th>To</th>
                <th>Status</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i}>
                  <td>
                    <code>{r.package}</code>
                  </td>
                  <td style={{ color: "var(--color-muted)", fontSize: "0.78rem" }}>
                    {r.source ?? "—"}
                  </td>
                  <td>
                    <code>{r.old ?? "—"}</code>
                  </td>
                  <td>
                    <code
                      style={
                        r.status === "updated"
                          ? { color: "var(--color-green)" }
                          : undefined
                      }
                    >
                      {r.new ?? "—"}
                    </code>
                  </td>
                  <td>{resultPill(r.status)}</td>
                  <td style={{ color: "var(--color-muted)", fontSize: "0.82rem" }}>
                    {r.notes ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Deferred majors */}
      {deferred.length > 0 && (
        <>
          <div className="section-title">Deferred Major Upgrades</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Package</th>
                  <th>From</th>
                  <th>To</th>
                  <th>Investigation Needed</th>
                </tr>
              </thead>
              <tbody>
                {deferred.map((d, i) => (
                  <tr key={i}>
                    <td>
                      <code>{d.package}</code>
                    </td>
                    <td>
                      <code>{d.from ?? "—"}</code>
                    </td>
                    <td>
                      <code>{d.to ?? "—"}</code>
                    </td>
                    <td style={{ fontSize: "0.82rem" }}>
                      {d.investigation_needed ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
