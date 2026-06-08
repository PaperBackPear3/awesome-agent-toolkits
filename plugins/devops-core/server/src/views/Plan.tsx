import React, { useState } from "react";
import type { App } from "@modelcontextprotocol/ext-apps";
import type { ClusterContext, PlanStep, BlockedItem, DecisionRow } from "../types";

interface PlanData {
  action: "plan";
  cluster: ClusterContext;
  decisions: DecisionRow[];
  plan: PlanStep[];
  blocked: BlockedItem[];
}

interface PlanViewProps {
  data: PlanData;
  app: App;
}

type ItemState = "pending" | "approved" | "skipped";

function decisionPill(decision: string) {
  const d = decision?.toLowerCase();
  if (d === "auto-plan") return <span className="status-pill status-ok">auto-plan</span>;
  if (d === "manual-review") return <span className="status-pill status-warn">manual-review</span>;
  if (d === "blocked") return <span className="status-pill status-block">blocked</span>;
  return <span className="status-pill status-skip">{decision}</span>;
}

export function PlanView({ data, app }: PlanViewProps) {
  const { cluster, plan, blocked, decisions } = data;

  const [states, setStates] = useState<Record<string, ItemState>>(() => {
    const init: Record<string, ItemState> = {};
    plan.forEach((s) => {
      // Default: auto-plan items start approved, manual-review start pending
      const dec = decisions.find((d) => d.package === s.package);
      init[s.package] = dec?.decision === "auto-plan" ? "approved" : "pending";
    });
    return init;
  });

  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState<{
    approved: string[];
    skipped: string[];
  } | null>(null);

  const toggle = (pkg: string, to: ItemState) => {
    setStates((prev) => ({ ...prev, [pkg]: prev[pkg] === to ? "pending" : to }));
  };

  const approvedList = plan.filter((s) => states[s.package] === "approved").map((s) => s.package);
  const skippedList = plan.filter((s) => states[s.package] === "skipped").map((s) => s.package);
  const pendingCount = plan.filter((s) => states[s.package] === "pending").length;

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await app.callServerTool({ name: "eks_confirm_plan", arguments: {
        approved: approvedList,
        skipped: skippedList,
      } });
      setConfirmed({ approved: approvedList, skipped: skippedList });
    } catch {
      // Keep UI open so user can retry
    } finally {
      setConfirming(false);
    }
  };

  if (confirmed) {
    return (
      <div className="view">
        <div className="step-panel" style={{ textAlign: "center", padding: "2rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>📋</div>
          <h2 style={{ marginBottom: "0.75rem" }}>Plan Confirmed</h2>
          <p style={{ color: "var(--color-muted)", fontSize: "0.875rem", marginBottom: "1rem" }}>
            The agent will now execute the approved items one at a time.
          </p>
          <div
            style={{
              display: "flex",
              gap: "0.75rem",
              justifyContent: "center",
              flexWrap: "wrap",
            }}
          >
            <span className="badge">
              <strong>✅ Approved</strong> {confirmed.approved.length}
            </span>
            <span className="badge">
              <strong>⏭ Skipped</strong> {confirmed.skipped.length}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="view">
      <div className="view-header">
        <h1>Update Plan</h1>
        <p className="subtitle">
          Review each item and approve or skip before the agent starts making changes.
        </p>
      </div>

      {/* Cluster bar */}
      <div className="cluster-bar">
        <span className="badge">
          <strong>Cluster</strong> {cluster.name}
        </span>
        <span className="badge">
          <strong>Region</strong> {cluster.region}
        </span>
        {cluster.k8s_version && (
          <span className="badge">
            <strong>K8s</strong> {cluster.k8s_version}
          </span>
        )}
      </div>

      {/* Plan items */}
      {plan.length === 0 ? (
        <p className="empty">No actionable items in this plan.</p>
      ) : (
        <div className="plan-list">
          {plan.map((step, i) => {
            const state = states[step.package] ?? "pending";
            const dec = decisions.find((d) => d.package === step.package);
            return (
              <div key={i} className={`plan-item ${state}`}>
                <div className="plan-item-body">
                  <div className="plan-item-title">
                    <span>{step.step ?? i + 1}.</span>
                    <code>{step.package}</code>
                    {dec && decisionPill(dec.decision)}
                    {step.from && step.to && (
                      <span className="plan-item-version">
                        {step.from} → {step.to}
                      </span>
                    )}
                  </div>
                  {step.file && (
                    <div className="plan-item-meta">
                      📄 <code>{step.file}</code>
                    </div>
                  )}
                  {step.rationale && (
                    <div className="plan-item-meta">{step.rationale}</div>
                  )}
                </div>
                <div className="plan-item-actions">
                  <button
                    className={`btn btn-approve ${state === "approved" ? "active" : ""}`}
                    onClick={() => toggle(step.package, "approved")}
                  >
                    {state === "approved" ? "✓ Approved" : "Approve"}
                  </button>
                  <button
                    className={`btn btn-skip ${state === "skipped" ? "active" : ""}`}
                    onClick={() => toggle(step.package, "skipped")}
                  >
                    {state === "skipped" ? "⏭ Skipped" : "Skip"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Blocked section */}
      {blocked.length > 0 && (
        <>
          <div className="section-title">Blocked</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {blocked.map((b, i) => (
                  <tr key={i}>
                    <td>
                      <code>{b.package}</code>
                    </td>
                    <td style={{ color: "var(--color-red)" }}>{b.reason ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Confirm bar */}
      {plan.length > 0 && (
        <div className="plan-confirm-bar">
          <div className="plan-confirm-counts">
            <span className="plan-count-chip">
              <span style={{ color: "var(--color-green)", fontWeight: 700 }}>
                ✅ {approvedList.length}
              </span>{" "}
              approved
            </span>
            <span className="plan-count-chip">
              <span style={{ color: "var(--color-gray)", fontWeight: 700 }}>
                ⏭ {skippedList.length}
              </span>{" "}
              skipped
            </span>
            {pendingCount > 0 && (
              <span className="plan-count-chip" style={{ color: "var(--color-muted)" }}>
                {pendingCount} undecided
              </span>
            )}
          </div>
          <button
            className="btn btn-primary"
            disabled={confirming || pendingCount > 0 || approvedList.length + skippedList.length === 0}
            onClick={handleConfirm}
            title={pendingCount > 0 ? "All items must be approved or skipped first" : undefined}
          >
            {confirming ? "Confirming…" : "Confirm Plan →"}
          </button>
        </div>
      )}
    </div>
  );
}
