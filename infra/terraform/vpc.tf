data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_vpcs" "existing" {
  count = var.create_networking || var.existing_vpc_id != "" ? 0 : 1

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

data "aws_subnets" "existing_public" {
  # Use plan-time-safe references (var + discovered) instead of local.vpc_id
  # which depends on aws_vpc.main[0].id and breaks destroy when VPC is gone.
  count = (!var.create_networking && length(var.existing_public_subnet_ids) == 0 && (var.existing_vpc_id != "" || local.discovered_vpc_id != "")) ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  filter {
    name   = "tag:Name"
    values = ["${var.project_name}-public-*"]
  }
}

data "aws_subnets" "existing_private" {
  # Use plan-time-safe references (var + discovered) instead of local.vpc_id
  # which depends on aws_vpc.main[0].id and breaks destroy when VPC is gone.
  count = (!var.create_networking && length(var.existing_private_subnet_ids) == 0 && (var.existing_vpc_id != "" || local.discovered_vpc_id != "")) ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  filter {
    name   = "tag:Name"
    values = ["${var.project_name}-private-*"]
  }
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  discovered_vpc_id = try(data.aws_vpcs.existing[0].ids[0], "")
  vpc_id            = var.create_networking ? aws_vpc.main[0].id : (var.existing_vpc_id != "" ? var.existing_vpc_id : local.discovered_vpc_id)

  discovered_public_subnet_ids  = try(data.aws_subnets.existing_public[0].ids, [])
  discovered_private_subnet_ids = try(data.aws_subnets.existing_private[0].ids, [])
  public_subnet_ids             = var.create_networking ? aws_subnet.public[*].id : (length(var.existing_public_subnet_ids) > 0 ? var.existing_public_subnet_ids : local.discovered_public_subnet_ids)
  private_subnet_ids            = var.create_networking ? aws_subnet.private[*].id : (length(var.existing_private_subnet_ids) > 0 ? var.existing_private_subnet_ids : local.discovered_private_subnet_ids)
}

check "existing_network_inputs" {
  assert {
    condition = var.create_networking || (
      local.vpc_id != "" &&
      length(local.public_subnet_ids) >= 2 &&
      length(local.private_subnet_ids) >= 2
    )

    error_message = "create_networking=false requires an existing VPC and at least two public/private subnets. Set existing_vpc_id + subnet IDs explicitly or tag existing subnets with ${var.project_name}-public-* and ${var.project_name}-private-*."
  }
}

# --- VPC ---
resource "aws_vpc" "main" {
  count = var.create_networking ? 1 : 0

  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.project_name}-vpc" }
}

# --- Public subnets (ALB + NAT) ---
resource "aws_subnet" "public" {
  count = var.create_networking ? 2 : 0

  vpc_id                  = aws_vpc.main[0].id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 1) # 10.0.1.0/24, 10.0.2.0/24
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = { Name = "${var.project_name}-public-${local.azs[count.index]}" }
}

# --- Private subnets (Fargate tasks) ---
resource "aws_subnet" "private" {
  count = var.create_networking ? 2 : 0

  vpc_id            = aws_vpc.main[0].id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10) # 10.0.10.0/24, 10.0.11.0/24
  availability_zone = local.azs[count.index]

  tags = { Name = "${var.project_name}-private-${local.azs[count.index]}" }
}

# --- Internet Gateway ---
resource "aws_internet_gateway" "main" {
  count = var.create_networking ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  tags = { Name = "${var.project_name}-igw" }
}

# --- NAT Gateway (single AZ, cost-optimized) ---
resource "aws_eip" "nat" {
  count = var.create_networking ? 1 : 0

  domain = "vpc"

  tags = { Name = "${var.project_name}-nat-eip" }
}

resource "aws_nat_gateway" "main" {
  count = var.create_networking ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id

  tags = { Name = "${var.project_name}-nat" }

  depends_on = [aws_internet_gateway.main]
}

# --- Route tables ---
resource "aws_route_table" "public" {
  count = var.create_networking ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }

  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public" {
  count = var.create_networking ? 2 : 0

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_route_table" "private" {
  count = var.create_networking ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[0].id
  }

  tags = { Name = "${var.project_name}-private-rt" }
}

resource "aws_route_table_association" "private" {
  count = var.create_networking ? 2 : 0

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[0].id
}
