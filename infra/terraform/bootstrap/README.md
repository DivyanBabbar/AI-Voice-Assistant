# Terraform Bootstrap

## Purpose

This directory is a **standalone Terraform project** whose only job is to create the
infrastructure that holds all other Terraform state.

## The Chicken-and-Egg Problem

Terraform stores its state in a remote backend (S3 + DynamoDB).
But to provision that S3 bucket and DynamoDB table, Terraform itself needs somewhere
to store *its own* state.

The solution: this bootstrap project uses **local state** (stored in
`terraform.tfstate` on disk, never committed to git). That is the one and only
exception to the "always use remote state" rule.

```
┌─────────────────────────────────────────────────────────────┐
│  bootstrap/                                                 │
│  ├── main.tf      ← provisions S3 bucket + DynamoDB table  │
│  └── terraform.tfstate  ← local, on disk, NOT in git       │
└─────────────────────────────────────────────────────────────┘
         │ creates
         ▼
┌─────────────────────────────────────────────────────────────┐
│  S3 bucket:  tfstate-hindi-voice-ai-<account-id>           │
│  DynamoDB:   tfstate-locks-hindi-voice-ai                  │
└─────────────────────────────────────────────────────────────┘
         │ used by
         ▼
┌─────────────────────────────────────────────────────────────┐
│  All other infra/terraform/* workspaces                    │
│  backend "s3" { bucket = "tfstate-hindi-voice-ai-..." }    │
└─────────────────────────────────────────────────────────────┘
```

## Run this exactly once

```bash
# From the repo root
cd infra/terraform/bootstrap

terraform init
terraform plan   # Expect ~3 resources: bucket, versioning, public-access-block,
                 #   encryption config, DynamoDB table (Terraform may count sub-resources).
# Review the plan, then:
terraform apply
```

After `apply` succeeds, note the output values and put them in the backend config of
every other Terraform workspace:

```hcl
terraform {
  backend "s3" {
    bucket         = "<state_bucket_name output>"
    key            = "<workspace>/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "tfstate-locks-hindi-voice-ai"
    encrypt        = true
  }
}
```

## What NOT to do

- Do **not** run `terraform destroy` on this project. Destroying the state bucket
  would make all other workspaces lose their state.
- Do **not** commit `terraform.tfstate` to git. It is already in `.gitignore`.
- Do **not** add this project to the main Terraform workspace. The circular dependency
  would break remote state initialisation.
