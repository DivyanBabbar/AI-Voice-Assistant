# modules/iam/variables.tf

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in 'owner/name' format. Used to scope the OIDC trust policy."
  type        = string
  default     = "arnavadarsh/voicebot"
}

variable "common_tags" {
  description = "Tags merged onto every resource in this module."
  type        = map(string)
  default     = {}
}
