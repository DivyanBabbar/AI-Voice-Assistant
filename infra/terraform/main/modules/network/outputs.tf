# modules/network/outputs.tf

output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the two public subnets."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the two private subnets."
  value       = aws_subnet.private[*].id
}

output "nat_instance_id" {
  description = "Instance ID of the NAT instance."
  value       = aws_instance.nat.id
}

output "nat_instance_public_ip" {
  description = "Public IP of the NAT instance (changes on stop/start unless EIP is added)."
  value       = aws_instance.nat.public_ip
}

output "s3_vpc_endpoint_id" {
  description = "ID of the S3 Gateway VPC endpoint."
  value       = aws_vpc_endpoint.s3.id
}
