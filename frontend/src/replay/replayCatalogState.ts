/**
 * replayCatalogState.ts — P3 UI State Contract
 *
 * Minimal state → badge mapping for replay catalog visibility states.
 * Do NOT mark ARTIFACT_CANDIDATE as ONLINE.
 * Do NOT mark RECONSTRUCTIBLE / REGISTERED_NO_DATA as replay success.
 */

export type CatalogVisibilityState =
  | "REGISTERED_WITH_REPLAY_ROWS"
  | "RECONSTRUCTIBLE"
  | "REGISTERED_NO_DATA"
  | "ARTIFACT_CANDIDATE"
  | "UNSUPPORTED";

export interface CatalogStateBadge {
  /** Short display label (English) */
  badge: string;
  /** Short display label (Chinese) */
  badgeZh: string;
  /** One-line summary for tooltip */
  summary: string;
  /** CSS variant / color class */
  variant: "success" | "info" | "warning" | "muted" | "disabled";
  /** True only for REGISTERED_WITH_REPLAY_ROWS */
  canShowReplayRows: boolean;
  /** True only for RECONSTRUCTIBLE */
  canEnterReconstructionQueue: boolean;
  /** True for NO_DATA / UNSUPPORTED */
  canShowNoDataMessage: boolean;
  /** True for ARTIFACT_CANDIDATE */
  isArtifactOnly: boolean;
}

export const CATALOG_STATE_BADGES: Record<CatalogVisibilityState, CatalogStateBadge> = {
  REGISTERED_WITH_REPLAY_ROWS: {
    badge: "Has replay rows",
    badgeZh: "可查看歷史預測",
    summary: "Strategy is registered and has historical replay rows.",
    variant: "success",
    canShowReplayRows: true,
    canEnterReconstructionQueue: false,
    canShowNoDataMessage: false,
    isArtifactOnly: false,
  },
  RECONSTRUCTIBLE: {
    badge: "Reconstructible",
    badgeZh: "可重建 / 尚未補資料",
    summary: "Artifact exists but replay rows not yet backfilled. Awaiting P5-P7.",
    variant: "info",
    canShowReplayRows: false,
    canEnterReconstructionQueue: true,
    canShowNoDataMessage: false,
    isArtifactOnly: false,
  },
  REGISTERED_NO_DATA: {
    badge: "No historical data",
    badgeZh: "無歷史資料",
    summary: "Strategy is registered but has no replay rows and no usable artifact.",
    variant: "warning",
    canShowReplayRows: false,
    canEnterReconstructionQueue: false,
    canShowNoDataMessage: true,
    isArtifactOnly: false,
  },
  ARTIFACT_CANDIDATE: {
    badge: "Artifact only",
    badgeZh: "Artifact only / 未進 runtime",
    summary: "Found in code/artifact scan only. NOT in runtime registry. Not ONLINE.",
    variant: "muted",
    canShowReplayRows: false,
    canEnterReconstructionQueue: false,
    canShowNoDataMessage: false,
    isArtifactOnly: true,
  },
  UNSUPPORTED: {
    badge: "Unsupported",
    badgeZh: "不支援",
    summary: "No artifact, no replay rows, no reconstruction path.",
    variant: "disabled",
    canShowReplayRows: false,
    canEnterReconstructionQueue: false,
    canShowNoDataMessage: true,
    isArtifactOnly: false,
  },
};

/** Resolve badge for a given visibility state. Falls back to UNSUPPORTED. */
export function getStateBadge(state: string): CatalogStateBadge {
  return (
    CATALOG_STATE_BADGES[state as CatalogVisibilityState] ??
    CATALOG_STATE_BADGES["UNSUPPORTED"]
  );
}

/** Guard: RECONSTRUCTIBLE must never be treated as replay success. */
export function assertNotReplaySuccess(state: CatalogVisibilityState): void {
  const badge = CATALOG_STATE_BADGES[state];
  if (badge.canShowReplayRows && state !== "REGISTERED_WITH_REPLAY_ROWS") {
    throw new Error(
      `State ${state} incorrectly flagged canShowReplayRows=true`
    );
  }
}
