# infra/terraform/main

Main Terraform stack for `hindi-voice-ai` in `ap-south-1` (Mumbai).
Builds the network, storage, and identity primitives that every application
module depends on.

## Prerequisites

- Terraform 1.7.5+ (`tfenv` or `.terraform-version` file)
- AWS CLI profile `admin` (SSO — run `aws sso login --profile admin` if the
  session has expired)
- Bootstrap stack already applied: S3 bucket `tfstate-hindi-voice-ai-106281192428`
  and DynamoDB table `tfstate-locks-hindi-voice-ai` must exist.

## How to run

```bash
cd infra/terraform/main

# Initialise — downloads provider and connects to the S3 backend.
terraform init

# Validate HCL syntax and configuration.
terraform validate

# Preview changes — always review before applying.
terraform plan -out=tfplan

# Apply (only after reviewing the plan).
terraform apply tfplan

# Check outputs.
terraform output
```

To target a non-default environment:

```bash
terraform plan -var="environment=staging" -out=tfplan
```

## What it creates

### network module

| Resource | Details |
|---|---|
| VPC | 10.0.0.0/16, ap-south-1 |
| Public subnets | 10.0.0.0/20 (1a) and 10.0.16.0/20 (1b) |
| Private subnets | 10.0.32.0/20 (1a) and 10.0.48.0/20 (1b) |
| Internet Gateway | Attached to VPC |
| NAT instance | t3.nano in public subnet 0 (see cost note below) |
| S3 VPC endpoint | Gateway type, free |

### storage module

| Resource | Details |
|---|---|
| `recordings-106281192428` | Versioned, lifecycle → Glacier IR @ 30 days, SSE-S3 |
| `exports-106281192428` | SSE-S3, no lifecycle rule |

Both buckets block all public access.

### iam module

| Resource | Details |
|---|---|
| `github-actions-terraform-dev` role | OIDC trust: repo `arnavadarsh/voicebot` |
| Inline policy | Scoped to tfstate S3/DynamoDB + VPC/EC2/S3/IAM actions for this stack |

## Cost breakdown

| Resource | Estimated monthly cost |
|---|---|
| VPC, subnets, IGW, route tables | **$0.00** |
| S3 Gateway VPC endpoint | **$0.00** |
| DynamoDB (PAY_PER_REQUEST, low volume) | **~$0.00** |
| S3 buckets (storage at our volume) | **~$0.00** |
| **t2.micro NAT instance** | **$0** (covered by free tier: 750 hrs/month for 12 months; ~$8.50/month after free-tier period ends) |
| Data transfer (intra-region, S3 via endpoint) | **$0.00** |

**Total: $0 on free tier (first 12 months). After the free-tier period the t2.micro
NAT instance charges ~$8.50/month if running 24/7.**

> **Action required before billing starts:** Replace the t2.micro NAT instance with
> a managed NAT Gateway. See `modules/network/README.md` for step-by-step instructions.

## Key design decisions

- **Backend hard-codes account ID.** Terraform backend blocks are evaluated before
  any provider or data source, so variables are unavailable. Account ID `106281192428`
  appears only in `backend.tf`; everywhere else it is derived from
  `data.aws_caller_identity.current`.

- **NAT instance instead of managed NAT Gateway.** Saves ~$32/month during
  development. Single point of failure — acceptable for a zero-traffic prototype.
  Must be replaced before production load.

- **S3 traffic bypasses NAT.** The S3 Gateway VPC endpoint (free) routes S3 API
  calls directly over the AWS backbone, so recordings uploads and exports downloads
  from private subnets do not incur NAT data-transfer charges.

- **SSE-S3 now, KMS in week 3.** AWS-managed AES-256 encryption is free. KMS adds
  ~$1/month per key plus per-request charges; deferred until the storage architecture
  is stable.

- **OIDC provider not managed here.** The GitHub OIDC provider was created by
  `scripts/aws-bootstrap.sh`. The IAM module references it via a data source to
  avoid an Terraform ownership conflict.

## Outputs

```
vpc_id                  = vpc-xxxxxxxxxxxxxxxxx
public_subnet_ids       = ["subnet-aaaa", "subnet-bbbb"]
private_subnet_ids      = ["subnet-cccc", "subnet-dddd"]
recordings_bucket_name  = recordings-106281192428
exports_bucket_name     = exports-106281192428
github_actions_role_arn = arn:aws:iam::106281192428:role/github-actions-terraform-dev
```
