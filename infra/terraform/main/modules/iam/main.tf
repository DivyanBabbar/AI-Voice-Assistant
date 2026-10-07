# modules/iam/main.tf
#
# GitHub Actions Terraform CI role.
#
# The GitHub OIDC provider was bootstrapped outside Terraform by
# scripts/aws-bootstrap.sh. We reference it via a data source to avoid an
# ownership conflict; do NOT re-create it here.
#
# Permissions are intentionally scoped to the minimum required to run
# `terraform plan` and `terraform apply` against infra/terraform/main/:
#   1. Read/write the remote state S3 bucket.
#   2. Lock/unlock the DynamoDB state table.
#   3. CRUD operations for every AWS resource managed in this stack:
#      VPC/EC2 networking, EC2 instances, S3 buckets, and IAM self-management.

data "aws_caller_identity" "current" {}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

locals {
  state_bucket_name = "tfstate-hindi-voice-ai-${data.aws_caller_identity.current.account_id}"
  lock_table_name   = "tfstate-locks-hindi-voice-ai"
  role_name         = "github-actions-terraform-${var.environment}"
  policy_name       = "github-actions-terraform-${var.environment}"
}

# ─── Trust policy ─────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    # Restrict to pushes/workflow_dispatch on any ref in this repo.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:*"]
    }

    # aud must be sts.amazonaws.com — this is the value GitHub Actions sends.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_actions_terraform" {
  name               = local.role_name
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json

  tags = merge(var.common_tags, {
    Name    = local.role_name
    Purpose = "terraform-ci"
  })
}

# ─── Permission policy ────────────────────────────────────────────────────────

data "aws_iam_policy_document" "github_actions_terraform_permissions" {
  # 1. Remote state — S3 bucket RW
  statement {
    sid    = "TerraformStateS3"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [
      "arn:aws:s3:::${local.state_bucket_name}",
      "arn:aws:s3:::${local.state_bucket_name}/*",
    ]
  }

  # 2. Remote state — DynamoDB lock table RW
  statement {
    sid    = "TerraformStateLock"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
    ]
    resources = [
      "arn:aws:dynamodb:*:${data.aws_caller_identity.current.account_id}:table/${local.lock_table_name}",
    ]
  }

  # 3. VPC and routing primitives
  statement {
    sid    = "VPCManagement"
    effect = "Allow"
    actions = [
      "ec2:CreateVpc",
      "ec2:DeleteVpc",
      "ec2:ModifyVpcAttribute",
      "ec2:DescribeVpcs",
      "ec2:DescribeVpcAttribute",
      "ec2:CreateSubnet",
      "ec2:DeleteSubnet",
      "ec2:ModifySubnetAttribute",
      "ec2:DescribeSubnets",
      "ec2:CreateInternetGateway",
      "ec2:DeleteInternetGateway",
      "ec2:AttachInternetGateway",
      "ec2:DetachInternetGateway",
      "ec2:DescribeInternetGateways",
      "ec2:CreateRouteTable",
      "ec2:DeleteRouteTable",
      "ec2:AssociateRouteTable",
      "ec2:DisassociateRouteTable",
      "ec2:CreateRoute",
      "ec2:DeleteRoute",
      "ec2:ReplaceRoute",
      "ec2:DescribeRouteTables",
      "ec2:CreateSecurityGroup",
      "ec2:DeleteSecurityGroup",
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:RevokeSecurityGroupIngress",
      "ec2:AuthorizeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupEgress",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSecurityGroupRules",
      "ec2:CreateTags",
      "ec2:DeleteTags",
      "ec2:DescribeTags",
    ]
    resources = ["*"]
  }

  # 4. EC2 instance (NAT) management
  statement {
    sid    = "EC2InstanceManagement"
    effect = "Allow"
    actions = [
      "ec2:RunInstances",
      "ec2:TerminateInstances",
      "ec2:StopInstances",
      "ec2:StartInstances",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeInstanceAttribute",
      "ec2:ModifyInstanceAttribute",
      "ec2:DescribeImages",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeRegions",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeNetworkInterfaceAttribute",
      "ec2:ModifyNetworkInterfaceAttribute",
    ]
    resources = ["*"]
  }

  # 5. S3 Gateway VPC endpoint management
  statement {
    sid    = "VPCEndpointManagement"
    effect = "Allow"
    actions = [
      "ec2:CreateVpcEndpoint",
      "ec2:DeleteVpcEndpoints",
      "ec2:ModifyVpcEndpoint",
      "ec2:DescribeVpcEndpoints",
      "ec2:DescribeVpcEndpointServices",
      "ec2:DescribePrefixLists",
    ]
    resources = ["*"]
  }

  # 6. S3 bucket lifecycle management (recordings + exports buckets)
  statement {
    sid    = "S3BucketManagement"
    effect = "Allow"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:GetBucketLocation",
      "s3:ListAllMyBuckets",
      "s3:GetBucketVersioning",
      "s3:PutBucketVersioning",
      "s3:GetBucketPublicAccessBlock",
      "s3:PutBucketPublicAccessBlock",
      "s3:GetEncryptionConfiguration",
      "s3:PutEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:PutLifecycleConfiguration",
      "s3:DeleteLifecycleConfiguration",
      "s3:GetBucketTagging",
      "s3:PutBucketTagging",
      "s3:GetBucketAcl",
      "s3:GetBucketObjectLockConfiguration",
      "s3:GetAccelerateConfiguration",
      "s3:GetBucketCORS",
      "s3:GetBucketLogging",
      "s3:GetBucketNotification",
      "s3:GetBucketRequestPayment",
      "s3:GetBucketWebsite",
    ]
    resources = ["*"]
  }

  # 7. IAM self-management: create/destroy the role and policy defined in this module.
  statement {
    sid    = "IAMSelfManagement"
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:UpdateRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:CreatePolicy",
      "iam:DeletePolicy",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:CreatePolicyVersion",
      "iam:DeletePolicyVersion",
      "iam:ListPolicyVersions",
      "iam:TagPolicy",
      "iam:UntagPolicy",
      "iam:GetOpenIDConnectProvider",
      "iam:ListOpenIDConnectProviders",
      "iam:PassRole",
    ]
    resources = ["*"]
  }

  # 8. STS — needed by Terraform data.aws_caller_identity at plan/apply time.
  statement {
    sid       = "STSGetCallerIdentity"
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "github_actions_terraform" {
  name        = local.policy_name
  description = "Scoped permissions for GitHub Actions to terraform plan/apply on infra/terraform/main/."
  policy      = data.aws_iam_policy_document.github_actions_terraform_permissions.json

  tags = merge(var.common_tags, {
    Name    = local.policy_name
    Purpose = "terraform-ci"
  })
}

resource "aws_iam_role_policy_attachment" "github_actions_terraform" {
  role       = aws_iam_role.github_actions_terraform.name
  policy_arn = aws_iam_policy.github_actions_terraform.arn
}
