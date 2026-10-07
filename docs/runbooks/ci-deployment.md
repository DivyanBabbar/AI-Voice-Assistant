# CI Deployment — Terraform Apply Gate

Explains how the `workflow_dispatch` apply gate works on free GitHub.

---

## Why not GitHub Environments?

GitHub Environment protection rules (required reviewers) are a **Pro/Team**
feature for private repositories. On the free plan the environment block in a
workflow is accepted but the approval gate is silently skipped, meaning apply
would run automatically on every push to main — which is not safe.

The apply workflow instead uses `workflow_dispatch` with a typed confirmation
input. Nothing applies unless you explicitly trigger it.

---

## How to trigger an apply

After a PR that touches `infra/**` is merged:

1. Go to **Actions → Terraform Apply** in the GitHub sidebar.
2. Click **Run workflow** (top-right of the workflow run list).
3. In the **confirm** field type exactly: `apply`
4. Click **Run workflow**.
5. The job runs `terraform init` then `terraform apply -auto-approve`.
6. Monitor the run; typical apply takes under 3 minutes.

If you type anything other than `apply` the job condition (`if: … == 'apply'`)
evaluates to false and the job is skipped — no apply happens.

---

## Rejecting / skipping an apply

Simply don't trigger the workflow. Terraform state is unchanged until you
explicitly run it.

---

## Secrets required

| Secret | Value | Where set |
|--------|-------|-----------|
| `AWS_ROLE_ARN` | `arn:aws:iam::106281192428:role/github-actions-oidc` | Repo Settings → Secrets |

The OIDC trust policy restricts issuance to this repository on any branch, so
no fork can assume the role.
