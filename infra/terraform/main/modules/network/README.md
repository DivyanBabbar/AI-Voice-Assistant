# network module

Creates the VPC, subnets, routing, and egress infrastructure for the
`hindi-voice-ai` platform in `ap-south-1`.

## What it creates

| Resource | Count | Notes |
|---|---|---|
| VPC | 1 | 10.0.0.0/16, DNS hostnames enabled |
| Public subnets | 2 | ap-south-1a and ap-south-1b, /20 each |
| Private subnets | 2 | ap-south-1a and ap-south-1b, /20 each |
| Internet Gateway | 1 | Attached to VPC |
| Public route table | 1 | 0.0.0.0/0 → IGW |
| Private route table | 1 | 0.0.0.0/0 → NAT instance ENI |
| NAT instance | 1 | t2.micro in public subnet 0 (free tier) |
| S3 Gateway VPC endpoint | 1 | Free; S3 traffic bypasses NAT |

## NAT strategy — FREE-TIER SHORTCUT

> **Replace with managed NAT once billing starts.**

A managed AWS NAT Gateway costs **~$32/month per AZ** plus $0.045/GB data
transfer. For a zero-budget prototype we use a single `t3.nano` EC2 instance
(~$3.50/month if running 24/7, but covered by the 750 free-tier hours for the
first 12 months for `t2.micro`/`t3.micro` — `t3.nano` is slightly below the
free tier, so actual cost may be ~$1.50–3.50/month depending on uptime).

The instance enables IP forwarding and `iptables MASQUERADE` via user data,
functioning as a basic NAT router.

**Trade-offs compared to managed NAT Gateway:**

| Concern | NAT Instance (t2.micro) | Managed NAT Gateway |
|---|---|---|
| Availability | Single point of failure | Highly available by default |
| Bandwidth | Limited by instance size | Scales automatically |
| Management | Requires OS patching | Fully managed |
| Cost (dev, free tier) | $0 for 12 months | ~$32+/month |
| Cost (after free tier) | ~$8.50/month | ~$32+/month |
| Free tier | Yes (750 hrs/month, 12 months) | No |

**How to replace:**

1. Remove `aws_instance.nat`, `aws_security_group.nat_instance`, and
   `aws_route.private_nat` from `main.tf`.
2. Add `aws_nat_gateway.main` in a public subnet with an associated EIP.
3. Update `aws_route.private_nat` to use `nat_gateway_id` instead of
   `network_interface_id`.
4. Run `terraform plan` and review before applying.

## S3 VPC Endpoint

An S3 **Gateway** endpoint is attached to both route tables. This is free
(no hourly charge, no data-transfer charge). Any S3 API call from inside
the VPC routes directly to S3 over the AWS backbone without touching the NAT
instance, keeping egress costs near zero for S3-heavy workloads.

## Subnet CIDR layout

```
10.0.0.0/16  ← VPC
├── 10.0.0.0/20   public-ap-south-1a
├── 10.0.16.0/20  public-ap-south-1b
├── 10.0.32.0/20  private-ap-south-1a
└── 10.0.48.0/20  private-ap-south-1b
```
