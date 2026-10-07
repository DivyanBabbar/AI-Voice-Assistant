# infra/terraform/main/main.tf
#
# Root module: instantiates network, storage, and IAM modules.
# All resource naming and tagging flows through common_tags from locals.tf.

data "aws_caller_identity" "current" {}

module "network" {
  source      = "./modules/network"
  environment = var.environment
  common_tags = local.common_tags
}

module "storage" {
  source      = "./modules/storage"
  account_id  = data.aws_caller_identity.current.account_id
  environment = var.environment
  common_tags = local.common_tags
}

module "iam" {
  source      = "./modules/iam"
  environment = var.environment
  common_tags = local.common_tags
}
