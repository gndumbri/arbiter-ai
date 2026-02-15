# Infrastructure Notes

## NAT Gateway Assessment

### Why outbound internet access is needed

Fargate tasks in private subnets need to reach:

1. **ECR** — to pull container images at task startup
2. **Secrets Manager** — to fetch secrets injected into task definitions
3. **CloudWatch Logs** — to ship container logs
4. **External SaaS APIs** — OpenAI, Anthropic, Pinecone, Supabase, Stripe, Cohere

Items 1-3 are required for tasks to even *start*. Item 4 is required for the app to function. Without outbound internet, ECS tasks will hang on launch and never become healthy.

However, a managed NAT gateway is not the only way to provide this connectivity.

### Current NAT gateway cost

- ~$32/month fixed (~$0.045/hr)
- ~$0.045/GB data processing on top of that
- Already optimized to a single-AZ NAT, but still the most expensive piece for a small deployment

### Options

#### Option 1: VPC Endpoints (eliminate NAT entirely)

Replace the NAT with **VPC Interface Endpoints** for AWS services, and move Fargate tasks to **public subnets** for external API calls.

**How it works:**

- Create VPC endpoints for ECR (2 endpoints: `ecr.api` + `ecr.dkr`), S3 (gateway endpoint, free), Secrets Manager, and CloudWatch Logs
- These give private subnets direct private connectivity to those AWS services — no NAT needed
- For external APIs (OpenAI, Stripe, etc.), move the Fargate tasks to public subnets with `assign_public_ip = true`

**Cost:**

- Interface endpoints: ~$7.30/month each (4 endpoints = ~$29/month) + $0.01/GB
- S3 gateway endpoint: free
- This actually **doesn't save much** over NAT if 4 interface endpoints are needed

**Verdict:** Not cost-effective unless the need for external API calls from the tasks can also be eliminated.

#### Option 2: Public subnets + `assign_public_ip = true` (recommended)

Move Fargate tasks from private subnets to public subnets and set `assign_public_ip = true`. Remove the NAT gateway entirely.

**How it works:**

- Tasks get a public IP and route outbound through the Internet Gateway directly
- Inbound security is still enforced by security groups — the ECS SG only allows traffic from the ALB SG, so tasks aren't "exposed" in any dangerous way
- RDS and ElastiCache stay in private subnets, only reachable from the ECS SG

**Cost:** $0. No NAT gateway, no VPC endpoints.

**Trade-offs:**

- Tasks have public IPs, but security groups block all unsolicited inbound traffic — equivalent protection to what exists today
- Slightly less "defense in depth" than private subnets — if someone misconfigured the SG, tasks would be directly reachable. In practice this is low risk for a small project.
- This is a very common pattern for cost-conscious Fargate deployments

**Verdict:** Best option for this scale. Saves ~$32+/month with minimal security trade-off.

#### Option 3: VPC Endpoints for AWS services + NAT Instance

Replace the managed NAT gateway with a `t4g.nano` EC2 instance running as a NAT.

**Cost:** ~$3/month for the instance vs ~$32/month for the gateway.

**Trade-offs:**

- Requires managing the instance (patching, monitoring, auto-recovery)
- Lower throughput and no built-in HA
- More Terraform complexity (EC2 instance, AMI, user data, source/dest check disabled)

**Verdict:** Only worth it if tasks must stay in private subnets without public IPs and cost savings are desired. More operational burden.

### Recommendation

**Option 2 (public subnets)** is the clear winner for this project. Running a single task per service on free-tier infrastructure with a single-AZ NAT is already a cost-conscious deployment. Moving tasks to public subnets saves the entire NAT cost, keeps the architecture simple, and security groups already enforce proper access control. RDS and Redis remain in private subnets, unreachable from the internet.
