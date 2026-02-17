data "aws_caller_identity" "current" {}

locals {
  existing_ecs_task_execution_role_name = var.existing_ecs_task_execution_role_name != "" ? var.existing_ecs_task_execution_role_name : "${var.project_name}-ecs-task-execution"
  existing_ecs_task_role_name           = var.existing_ecs_task_role_name != "" ? var.existing_ecs_task_role_name : "${var.project_name}-ecs-task"

  resolve_execution_role_via_data = !var.create_ecs_task_roles && (var.existing_ecs_task_execution_role_arn == "" || var.manage_ecs_task_role_policies)
  resolve_task_role_via_data      = !var.create_ecs_task_roles && (var.existing_ecs_task_role_arn == "" || var.manage_ecs_task_role_policies)
}

data "aws_iam_role" "existing_ecs_task_execution" {
  count = local.resolve_execution_role_via_data ? 1 : 0
  name  = local.existing_ecs_task_execution_role_name
}

data "aws_iam_role" "existing_ecs_task" {
  count = local.resolve_task_role_via_data ? 1 : 0
  name  = local.existing_ecs_task_role_name
}

locals {
  ecs_task_execution_role_arn = var.create_ecs_task_roles ? aws_iam_role.ecs_task_execution[0].arn : (
    var.existing_ecs_task_execution_role_arn != "" ? var.existing_ecs_task_execution_role_arn : data.aws_iam_role.existing_ecs_task_execution[0].arn
  )
  ecs_task_execution_role_name = var.create_ecs_task_roles ? aws_iam_role.ecs_task_execution[0].name : (
    var.existing_ecs_task_execution_role_name != "" ? var.existing_ecs_task_execution_role_name : data.aws_iam_role.existing_ecs_task_execution[0].name
  )
  ecs_task_role_arn = var.create_ecs_task_roles ? aws_iam_role.ecs_task[0].arn : (
    var.existing_ecs_task_role_arn != "" ? var.existing_ecs_task_role_arn : data.aws_iam_role.existing_ecs_task[0].arn
  )
  ecs_task_role_name = var.create_ecs_task_roles ? aws_iam_role.ecs_task[0].name : (
    var.existing_ecs_task_role_name != "" ? var.existing_ecs_task_role_name : data.aws_iam_role.existing_ecs_task[0].name
  )
  manage_task_role_policies = var.create_ecs_task_roles || var.manage_ecs_task_role_policies
}

check "ecs_task_roles_inputs" {
  assert {
    condition = var.create_ecs_task_roles || (
      local.ecs_task_execution_role_arn != "" &&
      local.ecs_task_role_arn != ""
    )
    error_message = "create_ecs_task_roles=false requires existing ECS task role ARNs or discoverable role names."
  }
}

# --- GitHub Actions OIDC (keyless auth for CI/CD) ---
resource "aws_iam_openid_connect_provider" "github_actions" {
  count = var.create_github_actions_iam ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_actions" {
  count = var.create_github_actions_iam ? 1 : 0
  name  = "${var.project_name}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github_actions[0].arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_actions" {
  count = var.create_github_actions_iam ? 1 : 0
  name  = "${var.project_name}-github-actions-deploy"
  role  = aws_iam_role.github_actions[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeRepositories",
          "ecr:ListTagsForResource",
          "ecr:TagResource",
          "ecr:GetLifecyclePolicy",
          "ecr:PutLifecyclePolicy",
          "ecr:DeleteLifecyclePolicy",
          "ecr:GetRepositoryPolicy",
          "ecr:SetRepositoryPolicy",
          "ecr:DescribeImages"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:CreateCluster",
          "ecs:DescribeClusters",
          "ecs:UpdateCluster",
          "ecs:DeleteCluster",
          "ecs:RegisterTaskDefinition",
          "ecs:DeregisterTaskDefinition",
          "ecs:DescribeTaskDefinition",
          "ecs:CreateService",
          "ecs:UpdateService",
          "ecs:DeleteService",
          "ecs:RunTask",
          "ecs:DescribeServices",
          "ecs:DescribeTasks",
          "ecs:TagResource",
          "ecs:ListTagsForResource",
          "ecs:ListServices",
          "ecs:ListClusters"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "rds:CreateDBInstance",
          "rds:DescribeDBInstances",
          "rds:ModifyDBInstance",
          "rds:DeleteDBInstance",
          "rds:CreateDBSubnetGroup",
          "rds:DescribeDBSubnetGroups",
          "rds:ModifyDBSubnetGroup",
          "rds:DeleteDBSubnetGroup",
          "rds:ListTagsForResource",
          "rds:AddTagsToResource",
          "rds:RemoveTagsFromResource"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "elasticache:CreateCacheCluster",
          "elasticache:DescribeCacheClusters",
          "elasticache:ModifyCacheCluster",
          "elasticache:DeleteCacheCluster",
          "elasticache:CreateCacheSubnetGroup",
          "elasticache:DescribeCacheSubnetGroups",
          "elasticache:ModifyCacheSubnetGroup",
          "elasticache:DeleteCacheSubnetGroup",
          "elasticache:ListTagsForResource",
          "elasticache:AddTagsToResource",
          "elasticache:RemoveTagsFromResource",
          "elasticache:DescribeCacheParameterGroups",
          "elasticache:DescribeCacheParameters"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = var.secrets_manager_arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::arbiter-ai-terraform-state",
          "arn:aws:s3:::arbiter-ai-terraform-state/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = "dynamodb:*"
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/arbiter-ai-terraform-lock"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:CreateTags",
          "ec2:DeleteTags",
          "ec2:Describe*",
          "elasticfilesystem:CreateFileSystem",
          "elasticfilesystem:DeleteFileSystem",
          "elasticfilesystem:DescribeFileSystems",
          "elasticfilesystem:CreateMountTarget",
          "elasticfilesystem:DeleteMountTarget",
          "elasticfilesystem:DescribeMountTargets",
          "elasticfilesystem:CreateAccessPoint",
          "elasticfilesystem:DeleteAccessPoint",
          "elasticfilesystem:DescribeAccessPoints",
          "elasticfilesystem:DescribeMountTargetSecurityGroups",
          "elasticfilesystem:TagResource",
          "elasticfilesystem:UntagResource",
          "elasticfilesystem:DescribeLifecycleConfiguration",
          "elasticfilesystem:PutLifecycleConfiguration",
          "elasticloadbalancing:Describe*",
          "elasticloadbalancing:CreateRule",
          "elasticloadbalancing:ModifyRule",
          "elasticloadbalancing:DeleteRule",
          "elasticloadbalancing:CreateListener",
          "elasticloadbalancing:ModifyListener",
          "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:CreateTargetGroup",
          "elasticloadbalancing:ModifyTargetGroup",
          "elasticloadbalancing:DeleteTargetGroup",
          "elasticloadbalancing:CreateLoadBalancer",
          "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:RegisterTargets",
          "elasticloadbalancing:DeregisterTargets",
          "elasticloadbalancing:SetSecurityGroups",
          "elasticloadbalancing:SetSubnets",
          "elasticloadbalancing:AddTags",
          "elasticloadbalancing:RemoveTags",
          "logs:*",
          "iam:GetRole",
          "iam:PassRole",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListAttachedRolePolicies",
          "iam:ListRolePolicies",
          "iam:GetRolePolicy",
          "iam:PutRolePolicy",
          "iam:GetOpenIDConnectProvider"
        ]
        Resource = "*"
      }
    ]
  })
}

# --- ECS Task Execution Role (used by ECS agent to pull images, write logs, read secrets) ---
resource "aws_iam_role" "ecs_task_execution" {
  count = var.create_ecs_task_roles ? 1 : 0
  name  = "${var.project_name}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  count = local.manage_task_role_policies ? 1 : 0

  role       = local.ecs_task_execution_role_name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_secrets_access" {
  count = local.manage_task_role_policies ? 1 : 0

  name = "${var.project_name}-secrets-access"
  role = local.ecs_task_execution_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = var.secrets_manager_arn
    }]
  })
}

# --- ECS Task Role (used by the running container) ---
resource "aws_iam_role" "ecs_task" {
  count = var.create_ecs_task_roles ? 1 : 0
  name  = "${var.project_name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# WHY: ECS Exec requires SSM permissions on the task role so the agent
# can open a session to the container (used for running migrations, debugging).
resource "aws_iam_role_policy" "ecs_task_ssm" {
  count = local.manage_task_role_policies ? 1 : 0

  name = "${var.project_name}-ecs-task-ssm"
  role = local.ecs_task_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ]
      Resource = "*"
    }]
  })
}

# WHY: Backend defaults to Bedrock for both LLM and embeddings.
# Task role must be allowed to invoke Bedrock foundation models.
resource "aws_iam_role_policy" "ecs_task_bedrock" {
  count = local.manage_task_role_policies ? 1 : 0

  name = "${var.project_name}-ecs-task-bedrock"
  role = local.ecs_task_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = [
        "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-5-sonnet-*",
        "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
      ]
    }]
  })
}
