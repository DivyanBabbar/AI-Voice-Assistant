# modules/network/variables.tf

variable "environment" {
  description = "Deployment environment."
  type        = string
}

variable "vpc_cidr" {
  description = "IPv4 CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Two AZs to spread subnets across."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "common_tags" {
  description = "Tags merged onto every resource in this module."
  type        = map(string)
  default     = {}
}
