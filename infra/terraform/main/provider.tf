# infra/terraform/main/provider.tf

provider "aws" {
  region = "ap-south-1"

  default_tags {
    tags = local.common_tags
  }
}
