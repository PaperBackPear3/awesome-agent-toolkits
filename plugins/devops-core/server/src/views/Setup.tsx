import React, { useState, useEffect } from "react";
import type { App } from "@modelcontextprotocol/ext-apps";
import type { KubeContext, AwsIdentity } from "../types";

interface SetupData {
  action: "setup";
  profiles: string[];
  activeProfile?: string;
  activeContext?: string;
  repoPaths?: string[];
}

interface SetupViewProps {
  data: SetupData;
  app: App;
}

type Step = "profile" | "context" | "confirm";

export function SetupView({ data, app }: SetupViewProps) {
  const [step, setStep] = useState<Step>("profile");
  const [profiles, setProfiles] = useState<string[]>(data.profiles);
  const [selectedProfile, setSelectedProfile] = useState(data.activeProfile ?? "");
  const [contexts, setContexts] = useState<KubeContext[]>([]);
  const [selectedContext, setSelectedContext] = useState(data.activeContext ?? "");
  const [identity, setIdentity] = useState<AwsIdentity | null>(null);
  const [tfRoot, setTfRoot] = useState(data.repoPaths?.[0] ?? "");
  const [loadingIdentity, setLoadingIdentity] = useState(false);
  const [loadingContexts, setLoadingContexts] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  // Refresh profiles if initially empty
  useEffect(() => {
    if (profiles.length === 0) {
      app
        .callServerTool("eks_list_profiles", {})
        .then((r) => {
          const c = r.structuredContent as { profiles?: string[] };
          if (c?.profiles?.length) {
            setProfiles(c.profiles);
            setSelectedProfile(c.profiles[0]);
          }
        })
        .catch(() => {});
    }
  }, []);

  // Fetch AWS identity when profile changes
  useEffect(() => {
    if (!selectedProfile) {
      setIdentity(null);
      return;
    }
    setLoadingIdentity(true);
    setIdentity(null);
    app
      .callServerTool("eks_get_identity", { profile: selectedProfile })
      .then((r) => setIdentity(r.structuredContent as AwsIdentity))
      .catch(() => setIdentity({ error: "Could not retrieve identity" }))
      .finally(() => setLoadingIdentity(false));
  }, [selectedProfile]);

  const loadContexts = async () => {
    setLoadingContexts(true);
    try {
      const r = await app.callServerTool("eks_list_contexts", {});
      const c = r.structuredContent as { contexts?: KubeContext[]; currentContext?: string };
      setContexts(c?.contexts ?? []);
      if (!selectedContext && c?.currentContext) setSelectedContext(c.currentContext);
    } catch {
      // leave empty — user will see alert
    } finally {
      setLoadingContexts(false);
      setStep("context");
    }
  };

  const handleConfirm = async () => {
    setConfirming(true);
    const ctx = contexts.find((c) => c.name === selectedContext);
    try {
      await app.callServerTool("eks_confirm_context", {
        cluster_name: ctx?.cluster ?? selectedContext,
        profile: selectedProfile || undefined,
        kube_context: selectedContext || undefined,
        tf_root: tfRoot || undefined,
      });
      setConfirmed(true);
    } catch {
      // show error but don't block
    } finally {
      setConfirming(false);
    }
  };

  const stepIndex = { profile: 1, context: 2, confirm: 3 }[step];

  if (confirmed) {
    return (
      <div className="view">
        <div className="step-panel" style={{ textAlign: "center", padding: "2rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>✅</div>
          <h2 style={{ marginBottom: "0.5rem" }}>Context Confirmed</h2>
          <p style={{ color: "var(--color-muted)", fontSize: "0.875rem" }}>
            The agent will continue with the selected cluster context.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="view">
      <div className="view-header">
        <h1>EKS Upgrade Setup</h1>
        <p className="subtitle">Select your AWS environment before starting the upgrade workflow</p>

        {/* Step indicator */}
        <div style={{ marginTop: "1rem" }}>
          <div className="step-indicator">
            <div className="step-dots">
              {([1, 2, 3] as const).map((n, i) => (
                <React.Fragment key={n}>
                  {i > 0 && (
                    <div className={`step-connector ${n - 1 < stepIndex ? "done" : ""}`} />
                  )}
                  <div
                    className={`step-dot ${
                      n < stepIndex ? "done" : n === stepIndex ? "active" : ""
                    }`}
                  >
                    {n < stepIndex ? "✓" : n}
                  </div>
                </React.Fragment>
              ))}
            </div>
          </div>
          <div className="step-labels">
            <span className="step-label">AWS Profile</span>
            <span className="step-label">kube Context</span>
            <span className="step-label">Confirm</span>
          </div>
        </div>
      </div>

      {/* ── Step 1: Profile ── */}
      {step === "profile" && (
        <div className="step-panel">
          <h2>Select AWS Profile</h2>

          {profiles.length === 0 ? (
            <div className="alert alert-warning">
              No AWS profiles detected. Ensure the AWS CLI is configured and try again.
            </div>
          ) : (
            <div className="profile-list">
              {profiles.map((p) => (
                <label
                  key={p}
                  className={`profile-item ${selectedProfile === p ? "selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="profile"
                    value={p}
                    checked={selectedProfile === p}
                    onChange={() => setSelectedProfile(p)}
                  />
                  <span className="profile-name">{p}</span>
                </label>
              ))}
            </div>
          )}

          {/* Identity preview */}
          <div className="identity-preview">
            {loadingIdentity && <span className="loading">Checking identity…</span>}
            {!loadingIdentity && identity?.error && (
              <span className="text-danger">⚠ {identity.error}</span>
            )}
            {!loadingIdentity && identity && !identity.error && (
              <div className="identity-info">
                <span className="badge">
                  <strong>Account</strong> {identity.Account}
                </span>
                <span
                  className="badge"
                  style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}
                  title={identity.Arn}
                >
                  <strong>ARN</strong>{" "}
                  {identity.Arn?.split("/").pop() ?? identity.Arn}
                </span>
              </div>
            )}
          </div>

          <div className="step-actions">
            <button
              className="btn btn-primary"
              disabled={!selectedProfile || loadingIdentity || loadingContexts}
              onClick={loadContexts}
            >
              {loadingContexts ? "Loading…" : "Next: Select Context →"}
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Context ── */}
      {step === "context" && (
        <div className="step-panel">
          <h2>Select kubeconfig Context</h2>

          {contexts.length === 0 ? (
            <div className="alert alert-warning">
              No kubeconfig contexts found. Run{" "}
              <code>kubectl config get-contexts</code> to verify your setup.
            </div>
          ) : (
            <div className="context-list">
              {contexts.map((ctx) => (
                <label
                  key={ctx.name}
                  className={`context-item ${selectedContext === ctx.name ? "selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="context"
                    value={ctx.name}
                    checked={selectedContext === ctx.name}
                    onChange={() => setSelectedContext(ctx.name)}
                  />
                  <div className="context-info">
                    <div className="context-name">
                      {ctx.name}
                      {ctx.current && (
                        <span className="badge badge-active">current</span>
                      )}
                    </div>
                    <div className="context-meta">
                      cluster: {ctx.cluster} · user: {ctx.user}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          )}

          <div className="step-actions">
            <button className="btn btn-secondary" onClick={() => setStep("profile")}>
              ← Back
            </button>
            <button
              className="btn btn-primary"
              disabled={!selectedContext}
              onClick={() => setStep("confirm")}
            >
              Next: Confirm →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3: Confirm ── */}
      {step === "confirm" && (
        <div className="step-panel">
          <h2>Confirm Context</h2>

          <div className="confirm-grid">
            <div className="confirm-row">
              <span className="confirm-label">AWS Profile</span>
              <code className="confirm-value">{selectedProfile || "default"}</code>
            </div>
            {identity && !identity.error && (
              <div className="confirm-row">
                <span className="confirm-label">AWS Account</span>
                <code className="confirm-value">{identity.Account}</code>
              </div>
            )}
            <div className="confirm-row">
              <span className="confirm-label">kubeconfig Context</span>
              <code className="confirm-value">{selectedContext}</code>
            </div>
            <div className="confirm-row">
              <span className="confirm-label">EKS Cluster</span>
              <code className="confirm-value">
                {contexts.find((c) => c.name === selectedContext)?.cluster ?? "—"}
              </code>
            </div>
          </div>

          <div className="tf-root-row">
            <label className="confirm-label" htmlFor="tf-root">
              Terraform root directory{" "}
              <span className="optional">(optional — helps the agent locate .tf files)</span>
            </label>
            <input
              id="tf-root"
              type="text"
              className="text-input"
              placeholder="/absolute/path/to/terraform"
              value={tfRoot}
              onChange={(e) => setTfRoot(e.target.value)}
            />
          </div>

          <div className="step-actions">
            <button className="btn btn-secondary" onClick={() => setStep("context")}>
              ← Back
            </button>
            <button
              className="btn btn-primary"
              disabled={confirming}
              onClick={handleConfirm}
            >
              {confirming ? "Confirming…" : "✓ Confirm & Continue"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
