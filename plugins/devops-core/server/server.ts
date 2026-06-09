import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  registerAppTool,
  registerAppResource,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import { execSync } from "child_process";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── Logging (stderr only — stdout is reserved for MCP JSON) ──────────────────

function log(level: "info" | "warn" | "error", message: string, data?: unknown) {
  const ts = new Date().toISOString();
  const line = data !== undefined
    ? `[devops-core] ${ts} ${level.toUpperCase()} ${message} ${JSON.stringify(data)}`
    : `[devops-core] ${ts} ${level.toUpperCase()} ${message}`;
  process.stderr.write(line + "\n");
}

const server = new McpServer({ name: "devops-core", version: "1.0.0" });

const RESOURCE_URI = "ui://eks-updater/mcp-app.html";

// ── Reusable Zod schemas ──────────────────────────────────────────────────────

const clusterSchema = z.object({
  name: z.string().describe("EKS cluster name"),
  region: z.string().describe("AWS region, e.g. us-east-1"),
  profile: z.string().optional().describe("AWS CLI named profile"),
  k8s_version: z.string().optional().describe("Current Kubernetes version"),
  account_id: z.string().optional(),
  tf_root: z.string().optional().describe("Path to Terraform root directory"),
});

const driftRowSchema = z.object({
  package: z.string(),
  declared: z.string().optional(),
  installed: z.string().optional(),
  status: z.string().describe("in-sync | declared-ahead | installed-ahead"),
});

const addonSchema = z.object({
  name: z.string(),
  current_version: z.string(),
  latest_version: z.string().optional(),
  status: z.string().optional(),
  is_default: z.boolean().optional(),
});

const helmReleaseSchema = z.object({
  name: z.string(),
  namespace: z.string(),
  chart: z.string(),
  version: z.string().optional(),
  app_version: z.string().optional(),
  status: z.string().optional(),
  updated: z.string().optional(),
});

const decisionRowSchema = z.object({
  package: z.string(),
  source: z.string().describe("terraform | addon | helm"),
  current: z.string().optional(),
  recommended: z.string().optional(),
  latest_stable: z.string().optional(),
  breaking: z.string().optional(),
  k8s_compatible: z.string().optional(),
  decision: z.string().describe("auto-plan | manual-review | blocked"),
  reason: z.string().optional(),
});

const planStepSchema = z.object({
  step: z.number().optional(),
  package: z.string(),
  file: z.string().optional(),
  from: z.string().optional(),
  to: z.string().optional(),
  rationale: z.string().optional(),
});

const blockedItemSchema = z.object({
  package: z.string(),
  reason: z.string().optional(),
});

const resultRowSchema = z.object({
  package: z.string(),
  source: z.string().optional(),
  old: z.string().optional(),
  new: z.string().optional(),
  status: z.string().describe("updated | skipped | deferred | blocked"),
  notes: z.string().optional(),
});

const deferredMajorSchema = z.object({
  package: z.string(),
  from: z.string().optional(),
  to: z.string().optional(),
  investigation_needed: z.string().optional(),
});

// ── Helper ────────────────────────────────────────────────────────────────────

function safeExec(cmd: string): { ok: boolean; output: string } {
  try {
    const out = execSync(cmd, { encoding: "utf-8", timeout: 15_000 }).trim();
    return { ok: true, output: out };
  } catch (err: unknown) {
    const output = err instanceof Error ? err.message : String(err);
    log("warn", `exec failed: ${cmd.split(" ")[0]}`, { cmd, error: output.slice(0, 200) });
    return { ok: false, output };
  }
}

// ── App tools (agent-invoked, render UI) ──────────────────────────────────────

// 1. eks_setup — context wizard
registerAppTool(
  server,
  "eks_setup",
  {
    description:
      "Open an interactive wizard that lets the user select an AWS profile, " +
      "pick a kubeconfig context, and confirm the cluster context before starting " +
      "an EKS upgrade run. Call at the start of Phase 1.",
    inputSchema: {
      profile: z.string().optional().describe("Pre-selected AWS CLI profile name"),
      repo_path: z
        .string()
        .optional()
        .describe("Absolute path to the Terraform/Kubernetes repository"),
    },
    _meta: { ui: { resourceUri: RESOURCE_URI } },
  },
  async (args) => {
    log("info", "tool:eks_setup", { profile: args.profile });
    const profilesResult = safeExec("aws configure list-profiles");
    const profiles = profilesResult.ok
      ? profilesResult.output.split("\n").filter(Boolean)
      : [];

    const contextResult = safeExec("kubectl config current-context");
    const activeContext = contextResult.ok ? contextResult.output : "";

    return {
      content: [
        {
          type: "text" as const,
          text: profiles.length
            ? `Found ${profiles.length} AWS profile(s). Use the interactive UI to select your profile and cluster context.`
            : "AWS CLI profiles not found — check CLI configuration. Use the UI to proceed.",
        },
      ],
      structuredContent: {
        action: "setup",
        profiles,
        activeProfile:
          args.profile ??
          (profiles.includes("default") ? "default" : (profiles[0] ?? "")),
        activeContext,
        repoPaths: args.repo_path ? [args.repo_path] : [],
      },
    };
  },
);

// 2. eks_inventory — inventory display
registerAppTool(
  server,
  "eks_inventory",
  {
    description:
      "Display the cluster inventory as interactive tables: drift between " +
      "Terraform-declared and installed add-on versions, installed add-ons, " +
      "and Helm releases. Call after Phase 2 inventory tools.",
    inputSchema: {
      cluster: clusterSchema,
      drift: z
        .array(driftRowSchema)
        .optional()
        .describe("Drift rows from Phase 2.4"),
      addons: z
        .array(addonSchema)
        .optional()
        .describe("Installed add-ons from inventory_addons.py"),
      helm_releases: z
        .array(helmReleaseSchema)
        .optional()
        .describe("Helm releases from inventory_helm.py"),
    },
    _meta: { ui: { resourceUri: RESOURCE_URI } },
  },
  async (args) => {
    log("info", "tool:eks_inventory", { cluster: args.cluster.name });
    const drift = args.drift ?? [];
    const addons = args.addons ?? [];
    const helm = args.helm_releases ?? [];
    const driftCount = drift.filter((r) => r.status !== "in-sync").length;

    return {
      content: [
        {
          type: "text" as const,
          text: [
            `Cluster: ${args.cluster.name} (${args.cluster.region}) · K8s ${args.cluster.k8s_version ?? "?"}`,
            `Add-ons: ${addons.length} installed`,
            `Helm releases: ${helm.length}`,
            driftCount
              ? `⚠️  ${driftCount} drift item(s) detected`
              : "✅ No version drift detected",
          ].join("\n"),
        },
      ],
      structuredContent: {
        action: "inventory",
        cluster: args.cluster,
        drift,
        addons,
        helm_releases: helm,
      },
    };
  },
);

// 3. eks_plan — interactive plan review
registerAppTool(
  server,
  "eks_plan",
  {
    description:
      "Present the update plan as an interactive checklist. The user can approve " +
      "or skip each item. When done, the UI calls eks_confirm_plan to record decisions. " +
      "Call after Phase 4.",
    inputSchema: {
      cluster: clusterSchema,
      decisions: z.array(decisionRowSchema).optional(),
      plan: z.array(planStepSchema).optional(),
      blocked: z.array(blockedItemSchema).optional(),
    },
    _meta: { ui: { resourceUri: RESOURCE_URI } },
  },
  async (args) => {
    log("info", "tool:eks_plan", { cluster: args.cluster.name, items: args.plan?.length ?? 0 });
    const plan = args.plan ?? [];
    const blocked = args.blocked ?? [];

    return {
      content: [
        {
          type: "text" as const,
          text: [
            `Update plan for cluster ${args.cluster.name}:`,
            `  ${plan.length} item(s) ready for review`,
            blocked.length ? `  ${blocked.length} blocked` : "",
            "Use the interactive UI to approve or skip each item, then click Confirm Plan.",
          ]
            .filter(Boolean)
            .join("\n"),
        },
      ],
      structuredContent: {
        action: "plan",
        cluster: args.cluster,
        decisions: args.decisions ?? [],
        plan,
        blocked,
      },
    };
  },
);

// 4. eks_summary — final summary display
registerAppTool(
  server,
  "eks_summary",
  {
    description:
      "Display the final upgrade summary with stat cards and a results table. " +
      "Call after Phase 6.",
    inputSchema: {
      cluster: clusterSchema,
      results: z.array(resultRowSchema).optional(),
      deferred_majors: z.array(deferredMajorSchema).optional(),
    },
    _meta: { ui: { resourceUri: RESOURCE_URI } },
  },
  async (args) => {
    log("info", "tool:eks_summary", { cluster: args.cluster.name });
    const results = args.results ?? [];
    const counts = { updated: 0, skipped: 0, deferred: 0, blocked: 0 };
    for (const r of results) {
      const s = r.status?.toLowerCase() as keyof typeof counts;
      if (s in counts) counts[s]++;
    }

    return {
      content: [
        {
          type: "text" as const,
          text: [
            `EKS upgrade complete — cluster ${args.cluster.name}:`,
            `  ✅ Updated:  ${counts.updated}`,
            `  ⏭️  Skipped:  ${counts.skipped}`,
            `  🔍 Deferred: ${counts.deferred}`,
            `  🔴 Blocked:  ${counts.blocked}`,
          ].join("\n"),
        },
      ],
      structuredContent: {
        action: "summary",
        cluster: args.cluster,
        results,
        deferred_majors: args.deferred_majors ?? [],
      },
    };
  },
);

// ── App-only tools (called from the UI, invisible to the model) ───────────────

registerAppTool(
  server,
  "eks_list_profiles",
  {
    description: "List available AWS CLI named profiles. Called by the setup wizard UI.",
    inputSchema: {},
    _meta: { ui: { resourceUri: RESOURCE_URI, visibility: ["app"] } },
  },
  async () => {
    const result = safeExec("aws configure list-profiles");
    const profiles = result.ok ? result.output.split("\n").filter(Boolean) : [];
    return {
      content: [{ type: "text" as const, text: JSON.stringify(profiles) }],
      structuredContent: { profiles },
    };
  },
);

registerAppTool(
  server,
  "eks_list_contexts",
  {
    description:
      "List kubeconfig contexts with cluster and user info. Called by the setup wizard UI.",
    inputSchema: {},
    _meta: { ui: { resourceUri: RESOURCE_URI, visibility: ["app"] } },
  },
  async () => {
    const result = safeExec("kubectl config view -o json");
    if (!result.ok) {
      return {
        content: [{ type: "text" as const, text: JSON.stringify({ error: result.output }) }],
        structuredContent: { contexts: [], currentContext: "" },
      };
    }
    type RawKubeConfig = {
      "current-context"?: string;
      contexts?: Array<{
        name: string;
        context?: { cluster?: string; user?: string };
      }>;
    };
    const kube = JSON.parse(result.output) as RawKubeConfig;
    const currentContext = kube["current-context"] ?? "";
    const contexts = (kube.contexts ?? []).map((c) => ({
      name: c.name,
      cluster: c.context?.cluster ?? "",
      user: c.context?.user ?? "",
      current: c.name === currentContext,
    }));
    return {
      content: [
        { type: "text" as const, text: JSON.stringify({ contexts, currentContext }) },
      ],
      structuredContent: { contexts, currentContext },
    };
  },
);

registerAppTool(
  server,
  "eks_get_identity",
  {
    description:
      "Get AWS caller identity (account ID, ARN) for the selected profile. " +
      "Called by the setup wizard UI to show which account is active.",
    inputSchema: {
      profile: z.string().optional().describe("AWS CLI profile name"),
    },
    _meta: { ui: { resourceUri: RESOURCE_URI, visibility: ["app"] } },
  },
  async (args) => {
    const profileFlag = args.profile ? `--profile ${args.profile}` : "";
    const result = safeExec(
      `aws sts get-caller-identity ${profileFlag} --output json`,
    );
    if (!result.ok) {
      return {
        content: [{ type: "text" as const, text: JSON.stringify({ error: result.output }) }],
        structuredContent: { error: result.output },
      };
    }
    const identity = JSON.parse(result.output) as {
      Account: string;
      Arn: string;
      UserId: string;
    };
    return {
      content: [{ type: "text" as const, text: JSON.stringify(identity) }],
      structuredContent: identity,
    };
  },
);

registerAppTool(
  server,
  "eks_confirm_context",
  {
    description:
      "Record the user-confirmed cluster context. The setup wizard UI calls " +
      "this when the user clicks 'Confirm & Continue'. The agent uses the " +
      "returned structuredContent as the authoritative context for Phase 2+.",
    inputSchema: {
      cluster_name: z.string().describe("EKS cluster name derived from the kubeconfig context"),
      region: z
        .string()
        .optional()
        .describe("AWS region (may be empty; agent verifies via describe-cluster)"),
      profile: z.string().optional(),
      k8s_version: z.string().optional(),
      kube_context: z.string().optional().describe("Selected kubeconfig context name"),
      tf_root: z.string().optional().describe("Terraform root directory path"),
    },
    _meta: { ui: { resourceUri: RESOURCE_URI, visibility: ["app"] } },
  },
  async (args) => {
    return {
      content: [
        {
          type: "text" as const,
          text: [
            "✅ Context confirmed by user:",
            `  Cluster:  ${args.cluster_name}`,
            `  Region:   ${args.region ?? "(detect via describe-cluster)"}`,
            `  Profile:  ${args.profile ?? "default"}`,
            `  K8s:      ${args.k8s_version ?? "(detect)"}`,
            `  Context:  ${args.kube_context ?? ""}`,
            `  TF root:  ${args.tf_root ?? "not specified"}`,
          ].join("\n"),
        },
      ],
      structuredContent: { confirmed: true, ...args },
    };
  },
);

registerAppTool(
  server,
  "eks_confirm_plan",
  {
    description:
      "Record which plan items the user approved vs skipped. The plan UI " +
      "calls this when the user clicks 'Confirm Plan'. The agent proceeds " +
      "only with approved items.",
    inputSchema: {
      approved: z.array(z.string()).describe("Package names the user approved"),
      skipped: z.array(z.string()).describe("Package names the user skipped"),
    },
    _meta: { ui: { resourceUri: RESOURCE_URI, visibility: ["app"] } },
  },
  async (args) => {
    return {
      content: [
        {
          type: "text" as const,
          text: [
            "📋 Plan confirmed by user:",
            `  ✅ Approved (${args.approved.length}): ${args.approved.join(", ") || "none"}`,
            `  ⏭️  Skipped  (${args.skipped.length}): ${args.skipped.join(", ") || "none"}`,
          ].join("\n"),
        },
      ],
      structuredContent: { confirmed: true, approved: args.approved, skipped: args.skipped },
    };
  },
);

// ── Resource registration ─────────────────────────────────────────────────────

registerAppResource(
  server,
  "EKS Updater UI",
  RESOURCE_URI,
  { description: "Interactive EKS upgrade UI" },
  async () => {
    log("info", "resource:read", { uri: RESOURCE_URI });
    const html = readFileSync(
      resolve(__dirname, "dist", "mcp-app.html"),
      "utf-8",
    );
    return {
      contents: [{ uri: RESOURCE_URI, mimeType: RESOURCE_MIME_TYPE, text: html }],
    };
  },
);

// ── Start ─────────────────────────────────────────────────────────────────────

log("info", "server starting", { version: "1.0.0" });
const transport = new StdioServerTransport();
await server.connect(transport);
log("info", "server connected");
