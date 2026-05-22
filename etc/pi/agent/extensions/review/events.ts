import type { Target } from "../lib/git";

export const REVIEW_WORKFLOW_EVENT_NAME = "review";
export const WORKFLOW_STARTED_EVENT = "workflow:started";
export const WORKFLOW_COMPLETED_EVENT = "workflow:completed";
export const WORKFLOW_FAILED_EVENT = "workflow:failed";
export const WORKFLOW_CANCELLED_EVENT = "workflow:cancelled";

export type ReviewWorkflowLifecycleStatus =
  | "started"
  | "completed"
  | "failed"
  | "cancelled";

export type ReviewWorkflowEventName =
  `workflow:${ReviewWorkflowLifecycleStatus}`;

export const REVIEW_WORKFLOW_LIFECYCLE_EVENTS: Record<
  ReviewWorkflowLifecycleStatus,
  ReviewWorkflowEventName
> = {
  started: WORKFLOW_STARTED_EVENT,
  completed: WORKFLOW_COMPLETED_EVENT,
  failed: WORKFLOW_FAILED_EVENT,
  cancelled: WORKFLOW_CANCELLED_EVENT,
};

export type ReviewWorkflowLifecycleEventHeader = {
  name: typeof REVIEW_WORKFLOW_EVENT_NAME;
  status: ReviewWorkflowLifecycleStatus;
};

export type ReviewWorkflowLifecycleEvent =
  ReviewWorkflowLifecycleEventHeader & {
    runId: string;
    cwd: string;
    targets: Target[];
    phaseCount: number;
    noFix: boolean;
    reason?: string;
    error?: string;
  };

export function reviewWorkflowEventName(
  status: ReviewWorkflowLifecycleStatus,
): ReviewWorkflowEventName {
  return REVIEW_WORKFLOW_LIFECYCLE_EVENTS[status];
}

export function isReviewWorkflowLifecycleEvent(
  data: unknown,
  expectedStatus: ReviewWorkflowLifecycleStatus,
): data is ReviewWorkflowLifecycleEventHeader {
  return (
    typeof data === "object" &&
    data !== null &&
    (data as Partial<ReviewWorkflowLifecycleEventHeader>).name ===
      REVIEW_WORKFLOW_EVENT_NAME &&
    (data as Partial<ReviewWorkflowLifecycleEventHeader>).status ===
      expectedStatus
  );
}
