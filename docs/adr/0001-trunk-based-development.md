# ADR-0001: Use trunk-based development with short-lived feature branches

- **Status**: Accepted
- **Date**: 2026-05-18
- **Deciders**: Arnav Adarsh

---

## Context

The project is a solo/small-team startup build with a 10-day sprint cadence. We needed
to choose a branching strategy before wiring CI and branch-protection rules. The main
candidates were:

1. **Git-flow** — long-lived `develop`, `release/*`, and `hotfix/*` branches.
2. **GitHub Flow** — feature branches merged directly to `main` after PR review.
3. **Trunk-based development (TBD)** — very short-lived feature branches (≤ 1–2 days),
   merged to `main` via PR, no long-lived integration branches.

The project targets sub-2s call latency and must ship working telephony within 10 days.
Slow integration cycles and merge-queue overhead would directly delay that goal.

## Decision

We will use **trunk-based development**: `main` is always releasable, feature work happens
on branches named `day-N-session-M-<slug>` that live for at most one session, and every
merge to `main` goes through a PR that passes CI. There is no `develop` branch.

Rejected alternatives:
- **Git-flow**: too much ceremony for a 1–2 person team; long-lived branches increase
  merge conflicts and delay integration feedback.
- **Pure GitHub Flow** (no naming convention): rejected because session-scoped branch
  names give us a free audit trail aligned with the 10-day build plan.

## Consequences

### Positive
- `main` is always in a deployable state; any commit can be demoed to stakeholders.
- Short branches reduce merge conflicts and keep CI feedback fast.
- Branch naming convention (`day-N-session-M-<slug>`) links git history to the
  session-by-session build plan without extra tooling.
- Branch-protection rules (require PR + passing CI) enforce this discipline automatically.

### Negative
- Incomplete features must be hidden behind feature flags or kept out of `main` until
  they are safe to expose — this adds a small coordination overhead.
- No long-lived staging branch; staging deploys must be triggered from `main` tags
  or manual workflow dispatches.

### Neutral / follow-on work
- Branch-protection rules on `main` must be configured in GitHub repository settings
  (require PR, require status checks, require linear history).
- Each session creates one branch and one PR; the PR is merged and the branch deleted
  before starting the next session.
