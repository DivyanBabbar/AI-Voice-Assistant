# Terraform Workflow

How infra changes move from a developer's laptop to production.

---

## 1. Local iteration

Run `terraform plan` locally before opening a PR to catch errors fast.

```bash
cd infra/terraform/main
terraform init          # first time, or after provider changes
terraform fmt           # auto-format; CI checks this
terraform validate
terraform plan          # review before committing
```

AWS credentials: assume the `admin` SSO profile (`aws sso login --profile admin`).

---

## 2. PR with plan-in-comments

1. Push your branch and open a PR against `main`.
2. The **Terraform Plan** workflow triggers automatically on any path matching
   `infra/**`.
3. It runs `fmt -check → init → validate → plan` and posts the plan output as a
   sticky comment on the PR. Each new push updates the same comment.
4. Reviewers read the plan diff in the comment, then approve the PR.
5. Merge only after CI is green and the plan shows only the intended changes.

> **Rule:** no infra change merges to main without a reviewed plan comment.

---

## 3. Merge to main → apply (manual trigger)

1. After the PR is merged, go to **Actions → Terraform Apply → Run workflow**.
2. Type `apply` in the confirm box and click **Run workflow**.
3. The workflow runs `terraform apply -auto-approve`.
4. Monitor the Actions tab; apply typically completes in under 3 minutes for
   small changes.

> **Why `workflow_dispatch`?** GitHub Environment protection rules (required
> reviewers) are a Pro/Team feature for private repos. The confirm-box input
> provides equivalent explicit intent without needing an upgrade.

---

## 4. Emergency rollback

If a bad apply lands on main:

```bash
# 1. Revert the offending commit on a new branch
git revert <bad-commit-sha>
git push origin fix/revert-bad-infra

# 2. Open a PR; the plan comment will show the resources being restored.
# 3. Approve and merge.
# 4. The apply workflow re-runs and rolls infra back to the prior state.
```

> Terraform state is versioned in S3 (`tfstate-hindi-voice-ai-106281192428`).
> If you need to recover a specific state version, see
> [disaster-recovery.md](disaster-recovery.md).

---

## Reference

| Resource | Value |
|----------|-------|
| State bucket | `tfstate-hindi-voice-ai-106281192428` |
| Lock table | `tfstate-locks-hindi-voice-ai` |
| OIDC role | `arn:aws:iam::106281192428:role/github-actions-oidc` |
| Terraform version | 1.7.5 (pinned in `.terraform-version`) |
| Apply environment | `production-infra` (repo Settings → Environments) |
