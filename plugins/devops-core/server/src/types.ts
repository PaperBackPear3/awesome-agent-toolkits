export interface ClusterContext {
  name: string;
  region: string;
  profile?: string;
  k8s_version?: string;
  account_id?: string;
  tf_root?: string;
}

export interface DriftRow {
  package: string;
  declared?: string;
  installed?: string;
  status: string;
}

export interface AddonInfo {
  name: string;
  current_version: string;
  latest_version?: string;
  status?: string;
  is_default?: boolean;
}

export interface HelmRelease {
  name: string;
  namespace: string;
  chart: string;
  version?: string;
  app_version?: string;
  status?: string;
  updated?: string;
}

export interface DecisionRow {
  package: string;
  source: string;
  current?: string;
  recommended?: string;
  latest_stable?: string;
  breaking?: string;
  k8s_compatible?: string;
  decision: string;
  reason?: string;
}

export interface PlanStep {
  step?: number;
  package: string;
  file?: string;
  from?: string;
  to?: string;
  rationale?: string;
}

export interface BlockedItem {
  package: string;
  reason?: string;
}

export interface ResultRow {
  package: string;
  source?: string;
  old?: string;
  new?: string;
  status: string;
  notes?: string;
}

export interface DeferredMajor {
  package: string;
  from?: string;
  to?: string;
  investigation_needed?: string;
}

export interface KubeContext {
  name: string;
  cluster: string;
  user: string;
  current: boolean;
}

export interface AwsIdentity {
  Account?: string;
  Arn?: string;
  UserId?: string;
  error?: string;
}

export type ViewInput =
  | {
      action: "setup";
      profiles: string[];
      activeProfile?: string;
      activeContext?: string;
      repoPaths?: string[];
    }
  | {
      action: "inventory";
      cluster: ClusterContext;
      drift: DriftRow[];
      addons: AddonInfo[];
      helm_releases: HelmRelease[];
    }
  | {
      action: "plan";
      cluster: ClusterContext;
      decisions: DecisionRow[];
      plan: PlanStep[];
      blocked: BlockedItem[];
    }
  | {
      action: "summary";
      cluster: ClusterContext;
      results: ResultRow[];
      deferred_majors: DeferredMajor[];
    };
