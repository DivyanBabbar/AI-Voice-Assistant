# modules/storage/variables.tf

variable "account_id" {
  description = "AWS account ID — appended to bucket names for global uniqueness."
  type        = string
}

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "common_tags" {
  description = "Tags merged onto every resource in this module."
  type        = map(string)
  default     = {}
}
