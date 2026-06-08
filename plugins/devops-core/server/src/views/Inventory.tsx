import React, { useState } from "react";
import type { ClusterContext, DriftRow, AddonInfo, HelmRelease } from "../types";

interface InventoryData {
  action: "inventory";
  cluster: ClusterContext;
  drift: DriftRow[];
  addons: AddonInfo[];
  helm_releases: HelmRelease[];
}

interface InventoryViewProps {
  data: InventoryData;
}

type Tab = "drift" | "addons" | "helm";

function driftPill(status: string) {
  const s = status.toLowerCase();
  if (s === "in-sync") return <span className="status-pill status-ok">in-sync</span>;
  if (s === "declared-ahead")
    return <span className="status-pill status-warn">declared-ahead</span>;
  if (s === "installed-ahead")
    return <span className="status-pill status-info">installed-ahead</span>;
  return <span className="status-pill status-skip">{status}</span>;
}

function addonStatusPill(status?: string) {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s === "active") return <span className="status-pill status-ok">active</span>;
  if (s === "degraded") return <span className="status-pill status-block">{status}</span>;
  return <span className="status-pill status-skip">{status}</span>;
}

function helmStatusPill(status?: string) {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s === "deployed") return <span className="status-pill status-ok">deployed</span>;
  if (s === "failed") return <span className="status-pill status-block">failed</span>;
  if (s === "pending-upgrade")
    return <span className="status-pill status-warn">pending-upgrade</span>;
  return <span className="status-pill status-skip">{status}</span>;
}

export function InventoryView({ data }: InventoryViewProps) {
  const [tab, setTab] = useState<Tab>("drift");

  const driftIssues = data.drift.filter((r) => r.status !== "in-sync").length;
  const { cluster, drift, addons, helm_releases: helm } = data;

  return (
    <div className="view">
      <div className="view-header">
        <h1>Cluster Inventory</h1>
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

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${tab === "drift" ? "active" : ""}`}
          onClick={() => setTab("drift")}
        >
          Drift
          {driftIssues > 0 ? (
            <span className="tab-count" style={{ background: "var(--color-yellow)", color: "white" }}>
              {driftIssues}
            </span>
          ) : (
            <span className="tab-count">{drift.length}</span>
          )}
        </button>
        <button
          className={`tab ${tab === "addons" ? "active" : ""}`}
          onClick={() => setTab("addons")}
        >
          Add-ons <span className="tab-count">{addons.length}</span>
        </button>
        <button
          className={`tab ${tab === "helm" ? "active" : ""}`}
          onClick={() => setTab("helm")}
        >
          Helm Releases <span className="tab-count">{helm.length}</span>
        </button>
      </div>

      {/* ── Drift tab ── */}
      {tab === "drift" && (
        <>
          {drift.length === 0 ? (
            <p className="empty">No drift data available.</p>
          ) : driftIssues === 0 ? (
            <p className="empty" style={{ fontStyle: "normal", color: "var(--color-green)" }}>
              ✅ All declared and installed versions are in sync.
            </p>
          ) : null}

          {drift.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Package</th>
                    <th>Declared (Terraform)</th>
                    <th>Installed (AWS)</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {drift.map((row, i) => (
                    <tr key={i}>
                      <td>
                        <code>{row.package}</code>
                      </td>
                      <td>
                        <code>{row.declared ?? "—"}</code>
                      </td>
                      <td>
                        <code>{row.installed ?? "—"}</code>
                      </td>
                      <td>{driftPill(row.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Add-ons tab ── */}
      {tab === "addons" && (
        <>
          {addons.length === 0 ? (
            <p className="empty">No add-ons found.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Add-on</th>
                    <th>Installed Version</th>
                    <th>Latest Compatible</th>
                    <th>Status</th>
                    <th>Default?</th>
                  </tr>
                </thead>
                <tbody>
                  {addons.map((a, i) => {
                    const outdated =
                      a.latest_version && a.current_version !== a.latest_version;
                    return (
                      <tr key={i}>
                        <td>
                          <code>{a.name}</code>
                        </td>
                        <td>
                          <code
                            style={outdated ? { color: "var(--color-yellow)" } : undefined}
                          >
                            {a.current_version}
                          </code>
                        </td>
                        <td>
                          <code>{a.latest_version ?? "—"}</code>
                        </td>
                        <td>{addonStatusPill(a.status)}</td>
                        <td style={{ color: "var(--color-muted)", fontSize: "0.78rem" }}>
                          {a.is_default ? "yes" : "no"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Helm tab ── */}
      {tab === "helm" && (
        <>
          {helm.length === 0 ? (
            <p className="empty">No Helm releases found in current context.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Release</th>
                    <th>Namespace</th>
                    <th>Chart</th>
                    <th>Version</th>
                    <th>App Version</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {helm.map((r, i) => (
                    <tr key={i}>
                      <td>
                        <code>{r.name}</code>
                      </td>
                      <td>
                        <code>{r.namespace}</code>
                      </td>
                      <td>
                        <code>{r.chart}</code>
                      </td>
                      <td>
                        <code>{r.version ?? "—"}</code>
                      </td>
                      <td>
                        <code>{r.app_version ?? "—"}</code>
                      </td>
                      <td>{helmStatusPill(r.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
