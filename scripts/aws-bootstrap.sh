#!/usr/bin/env bash
# scripts/aws-bootstrap.sh
#
# One-time bootstrap for the hindi-voice-ai AWS account.
# Run this after completing docs/runbooks/aws-account-setup.md (SSO is configured).
#
# What this script does:
#   1. Verifies the current SSO identity (never runs as root).
#   2. Creates an OIDC identity provider for GitHub Actions (idempotent).
#   3. Creates an IAM role "github-actions-oidc" that GitHub Actions can assume
#      to deploy infrastructure on behalf of CI pipelines.
#   4. Attaches a scoped permissions policy (least-privilege for Terraform).
#   5. Prints the role ARN — copy it into your GitHub Actions secrets.
#
# Idempotency: the script checks whether each resource already exists before
# creating it, so re-running it is safe and produces no duplicates.
#
# Prerequisites:
#   - AWS CLI v2 installed.
#   - An active SSO session: run `aws sso login --profile admin` first.
#   - The environment variable AWS_PROFILE=admin (or pass --profile admin manually).
#
# Usage:
#   export AWS_PROFILE=admin
#   bash scripts/aws-bootstrap.sh
#
# Expected output (last line):
#   ROLE_ARN=arn:aws:iam::<account-id>:role/github-actions-oidc

set -euo pipefail

# ─── constants ────────────────────────────────────────────────────────────────

# GitHub's OIDC provider URL — this is a fixed, well-known value published by GitHub.
GITHUB_OIDC_URL="https://token.actions.githubusercontent.com"

# The audience claim GitHub embeds in its OIDC tokens.
GITHUB_OIDC_AUDIENCE="sts.amazonaws.com"

# The IAM role name CI pipelines will assume.
ROLE_NAME="github-actions-oidc"

# Restrict which GitHub repo + branch can assume this role.
# Format: repo:<owner>/<repo>:ref:refs/heads/<branch>  (or use * for any branch)
# Change this to your actual org/repo before running.
GITHUB_SUBJECT="repo:arnavadarsh/hindi-voice-ai:ref:refs/heads/main"

# ─── step 1: verify identity ──────────────────────────────────────────────────

echo "==> Verifying AWS identity..."
IDENTITY=$(aws sts get-caller-identity --output json)
ACCOUNT_ID=$(echo "$IDENTITY" | python3 -c "import sys, json; print(json.load(sys.stdin)['Account'])")
CALLER_ARN=$(echo "$IDENTITY" | python3 -c "import sys, json; print(json.load(sys.stdin)['Arn'])")

echo "    Account ID : $ACCOUNT_ID"
echo "    Caller ARN : $CALLER_ARN"

# Abort if running as root — root should never be used programmatically.
if echo "$CALLER_ARN" | grep -q "root"; then
  echo "ERROR: You are running as the root user. Configure SSO and set AWS_PROFILE=admin."
  exit 1
fi

# ─── step 2: create GitHub Actions OIDC provider (idempotent) ─────────────────

echo ""
echo "==> Checking for GitHub OIDC provider..."

# List existing providers and check if GitHub's is already registered.
EXISTING_PROVIDERS=$(aws iam list-open-id-connect-providers --query 'OpenIDConnectProviderList[].Arn' --output text)
GITHUB_PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

if echo "$EXISTING_PROVIDERS" | grep -q "token.actions.githubusercontent.com"; then
  echo "    GitHub OIDC provider already exists — skipping creation."
else
  echo "    Creating GitHub OIDC provider..."
  # AWS auto-validates GitHub's TLS certificate thumbprint as of 2023.
  # We still supply the current known thumbprint for compatibility with older CLI versions.
  aws iam create-open-id-connect-provider \
    --url "$GITHUB_OIDC_URL" \
    --client-id-list "$GITHUB_OIDC_AUDIENCE" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" \
    > /dev/null
  echo "    GitHub OIDC provider created: $GITHUB_PROVIDER_ARN"
fi

# ─── step 3: create the IAM role (idempotent) ─────────────────────────────────

echo ""
echo "==> Checking for IAM role '$ROLE_NAME'..."

# The trust policy allows GitHub Actions (with the correct subject claim) to assume
# this role. The condition on token.sub restricts access to the specific repo + branch
# defined in GITHUB_SUBJECT above — anyone else's GitHub Actions cannot assume it.
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "$GITHUB_PROVIDER_ARN"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "$GITHUB_OIDC_AUDIENCE",
          "token.actions.githubusercontent.com:sub": "$GITHUB_SUBJECT"
        }
      }
    }
  ]
}
EOF
)

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

if aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
  echo "    Role '$ROLE_NAME' already exists — skipping creation."
else
  echo "    Creating IAM role '$ROLE_NAME'..."
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_POLICY" \
    --description "Assumed by GitHub Actions via OIDC for Terraform deployments" \
    > /dev/null
  echo "    Role created: $ROLE_ARN"
fi

# ─── step 4: attach a permissions policy (idempotent) ─────────────────────────

# This inline policy grants the minimum set of permissions Terraform needs to
# manage the state backend and to plan/apply infra in future sessions.
# It will be expanded incrementally as new AWS resources are introduced.
echo ""
echo "==> Attaching inline policy to role '$ROLE_NAME'..."

POLICY_NAME="TerraformDeploy"

# Check whether the inline policy already exists on the role.
EXISTING_POLICIES=$(aws iam list-role-policies --role-name "$ROLE_NAME" --query 'PolicyNames' --output text)

if echo "$EXISTING_POLICIES" | grep -q "$POLICY_NAME"; then
  echo "    Policy '$POLICY_NAME' already attached — skipping."
else
  INLINE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TerraformStateBackend",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::tfstate-hindi-voice-ai-${ACCOUNT_ID}",
        "arn:aws:s3:::tfstate-hindi-voice-ai-${ACCOUNT_ID}/*"
      ]
    },
    {
      "Sid": "TerraformStateLock",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:ap-south-1:${ACCOUNT_ID}:table/tfstate-locks-hindi-voice-ai"
    }
  ]
}
EOF
)

  aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    --policy-document "$INLINE_POLICY"
  echo "    Policy '$POLICY_NAME' attached."
fi

# ─── step 5: output ───────────────────────────────────────────────────────────

echo ""
echo "==> Bootstrap complete."
echo ""
echo "    Copy the following ARN into your GitHub repository secrets:"
echo "    Settings → Secrets and variables → Actions → New repository secret"
echo "    Name:  AWS_ROLE_ARN"
echo "    Value: $ROLE_ARN"
echo ""
echo "ROLE_ARN=$ROLE_ARN"
