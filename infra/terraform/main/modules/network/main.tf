# modules/network/main.tf
#
# Creates a VPC with 2 public + 2 private subnets across two AZs.
#
# NAT strategy — FREE-TIER SHORTCUT:
#   A managed NAT Gateway costs ~$32/month + data-transfer fees.
#   Instead we use a t3.nano EC2 instance with iptables masquerade.
#   See README.md for the full trade-off analysis and replacement instructions.
#
# S3 traffic from private subnets exits through the S3 Gateway VPC Endpoint
# (free, no data-transfer charge within region) rather than through the NAT
# instance, keeping egress costs near zero for S3-heavy workloads.

data "aws_region" "current" {}

# Latest Amazon Linux 2023 AMI — x86_64 for t3.nano compatibility.
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# ─── VPC ──────────────────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.common_tags, {
    Name = "vpc-hindi-voice-ai-${var.environment}"
  })
}

# ─── Internet Gateway ─────────────────────────────────────────────────────────

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.common_tags, {
    Name = "igw-hindi-voice-ai-${var.environment}"
  })
}

# ─── Subnets ──────────────────────────────────────────────────────────────────

# Public subnets — index 0 and 1 of /20 slices from the /16.
resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.common_tags, {
    Name = "subnet-public-${var.availability_zones[count.index]}-${var.environment}"
    Tier = "public"
  })
}

# Private subnets — index 2 and 3, keeping address space separate from public.
resource "aws_subnet" "private" {
  count = 2

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 2)
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.common_tags, {
    Name = "subnet-private-${var.availability_zones[count.index]}-${var.environment}"
    Tier = "private"
  })
}

# ─── Public route table ───────────────────────────────────────────────────────

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(var.common_tags, {
    Name = "rtb-public-${var.environment}"
  })
}

resource "aws_route_table_association" "public" {
  count = 2

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ─── NAT instance (free-tier shortcut) ───────────────────────────────────────

resource "aws_security_group" "nat_instance" {
  name_prefix = "nat-${var.environment}-"
  vpc_id      = aws_vpc.main.id
  description = "NAT instance: accepts all VPC-internal traffic, allows all egress."

  ingress {
    description = "All traffic from VPC CIDR"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "Unrestricted outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.common_tags, {
    Name = "sg-nat-instance-${var.environment}"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_instance" "nat" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t2.micro"
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.nat_instance.id]
  associate_public_ip_address = true

  # Disabling source/dest check is required for an EC2 instance to forward packets
  # on behalf of other hosts (i.e. act as a router/NAT).
  source_dest_check = false

  user_data = base64encode(<<-EOF
    #!/bin/bash
    # Enable IP forwarding and set up iptables masquerade for NAT.
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    sysctl -p
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    # Persist across reboots (Amazon Linux 2023 uses iptables-save service).
    iptables-save > /etc/sysconfig/iptables 2>/dev/null || true
  EOF
  )

  tags = merge(var.common_tags, {
    Name = "nat-instance-${var.environment}"
    Role = "nat"
  })
}

# ─── Private route table — default route via NAT instance ────────────────────

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.common_tags, {
    Name = "rtb-private-${var.environment}"
  })
}

# Route all non-S3 traffic from private subnets through the NAT instance ENI.
# S3 traffic is handled by the Gateway VPC endpoint below (free path).
resource "aws_route" "private_nat" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  network_interface_id   = aws_instance.nat.primary_network_interface_id
}

resource "aws_route_table_association" "private" {
  count = 2

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ─── S3 Gateway VPC Endpoint ──────────────────────────────────────────────────
#
# Gateway endpoints are free (no hourly charge, no data-transfer charge for
# traffic that stays within the region). They work by injecting a prefix list
# into the route table, so S3 traffic from private subnets never hits the NAT
# instance and incurs no data-transfer cost.

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = [
    aws_route_table.private.id,
    aws_route_table.public.id,
  ]

  tags = merge(var.common_tags, {
    Name = "vpce-s3-${var.environment}"
  })
}
