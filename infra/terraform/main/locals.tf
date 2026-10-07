# infra/terraform/main/locals.tf

locals {
  common_tags = {
    Project     = "hindi-voice-ai"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
