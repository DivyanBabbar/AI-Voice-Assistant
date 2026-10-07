# Disaster Recovery — Terraform Infrastructure

Placeholder. Each section will be expanded in Week 4.

---

## Scenario 1: tfstate bucket accidentally deleted

**What breaks:** All Terraform operations fail; state is unreachable.

**Recovery:** S3 versioning is enabled — restore the bucket from the S3 console
using a prior version, or re-create the bucket with the same name and import the
most recent state object from S3 version history. Re-run `terraform init` to
re-attach the backend.

---

## Scenario 2: OIDC trust misconfiguration

**What breaks:** GitHub Actions cannot assume the IAM role; all CI jobs that
touch AWS fail with `AccessDenied`.

**Recovery:** Log in via SSO (`aws sso login --profile admin`), open the IAM
console, navigate to the `github-actions-oidc` role, and correct the trust
policy condition (`StringLike` on `token.actions.githubusercontent.com:sub`).
Re-run the failing workflow once the policy is saved.

---

## Scenario 3: ap-south-1 region outage

**What breaks:** ECS tasks, RDS, and any regional services are unavailable;
Terraform state in S3 may also be temporarily unreachable.

**Recovery:** S3 state bucket is single-region; wait for AWS to restore the
region. For complete continuity, a cross-region state replica (us-east-1) and
DR VPC will be provisioned in Week 4. Monitor the AWS Health Dashboard and the
#oncall Slack channel.

---

_Last updated: 2026-05-21 — expand each section in Week 4 sprint._
