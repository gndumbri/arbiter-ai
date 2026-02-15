#!/usr/bin/env python3
"""Generate and verify infra inventory + Terraform permissions documentation."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_ROOT = REPO_ROOT / "infra"
OUTPUT_INVENTORY_PATH = INFRA_ROOT / "INFRA_INVENTORY.md"
OUTPUT_PERMISSION_MAP_PATH = INFRA_ROOT / "TERRAFORM_PERMISSION_MAP.md"

IGNORED_PARTS = {".terraform", "__pycache__"}

FOLDER_DETAILS: dict[str, tuple[str, str]] = {
    "infra": (
        "Infrastructure root. Shared docs, ECS templates, Terraform modules, and infra utility scripts.",
        "Documentation + configuration only.",
    ),
    "infra/ecs": (
        "Canonical ECS task definition templates for backend/frontend containers.",
        "No direct AWS API calls; consumed by deploy workflows and operator tooling.",
    ),
    "infra/scripts": (
        "Automation helpers for infra docs/validation used in CI and local checks.",
        "No direct AWS API calls; gates CI quality.",
    ),
    "infra/terraform": (
        "Terraform stack for ECS, ALB, networking, IAM, data services, EFS, SES, and outputs.",
        "Directly drives AWS resource creation/update/reuse based on create_* flags.",
    ),
    "infra/terraform/environments": (
        "Environment-specific tfvars profiles (for example, full sandbox bootstrap).",
        "Controls whether CI/Terraform needs create privileges or can reuse existing infra.",
    ),
}

TF_MODULES: list[tuple[str, str, str]] = [
    ("alb.tf", "ALB, listeners, listener rules, target groups, and existing-resource discovery.", "create_alb_resources"),
    ("cloudwatch.tf", "CloudWatch log groups for backend/frontend/worker/beat services.", "create_cloudwatch_log_groups"),
    ("ecr.tf", "ECR repositories and lifecycle policies for backend/frontend images.", "Always managed"),
    ("ecs.tf", "ECS cluster, task definitions, services, networking wiring, and runtime env/secrets contract.", "Always managed"),
    ("efs.tf", "Shared uploads EFS filesystem/access point/mount targets and EFS SG wiring.", "enable_shared_uploads + create_efs_resources"),
    ("elasticache.tf", "Redis SG, subnet group, and cluster for queue/cache backing services.", "create_data_services"),
    ("iam.tf", "OIDC, CI role, ECS execution/task roles, and task role policy attachments.", "create_github_actions_iam / create_ecs_task_roles / manage_ecs_task_role_policies"),
    ("imports.tf", "One-time import stanzas for pre-existing ECR repositories.", "Always evaluated"),
    ("outputs.tf", "Deployment outputs used by operators and downstream automation.", "Always evaluated"),
    ("providers.tf", "Provider + backend state configuration and global tagging defaults.", "Always evaluated"),
    ("rds.tf", "Postgres SG/subnet group/DB instance provisioning.", "create_data_services"),
    ("security_groups.tf", "ALB/ECS service security groups and SG-rule wiring with reuse mode.", "create_service_security_groups"),
    ("ses.tf", "SES domain identity + DKIM and ECS task SES send policy.", "ses_domain + email_provider"),
    ("variables.tf", "Terraform input contract, environment toggles, and validation rules.", "Always evaluated"),
    ("vpc.tf", "VPC/subnets/routes/NAT creation or discovery of existing network assets.", "create_networking"),
]

PERMISSION_MATRIX: list[tuple[str, str, str]] = [
    (
        "Always (Terraform state + service deploy path)",
        "S3 backend bucket, DynamoDB lock table, ECR image repos, ECS cluster/services/task defs, and read-only discovery APIs.",
        "s3:GetObject/PutObject/ListBucket, dynamodb:*, ecr:*, ecs:RegisterTaskDefinition/UpdateService/Describe*, ec2:Describe*, "
        "elasticloadbalancing:Describe*, logs:Describe*, iam:GetRole/PassRole/GetPolicy*",
    ),
    (
        "create_networking=true",
        "VPC, subnets, route tables, internet gateway, EIP, NAT gateway.",
        "ec2:CreateVpc/DeleteVpc/CreateSubnet/DeleteSubnet/CreateRouteTable/CreateRoute/CreateInternetGateway/AttachInternetGateway/"
        "AllocateAddress/ReleaseAddress/CreateNatGateway/DeleteNatGateway/CreateTags/DeleteTags + ec2:Describe*",
    ),
    (
        "create_service_security_groups=true",
        "ALB/ECS security groups and SG rules.",
        "ec2:CreateSecurityGroup/DeleteSecurityGroup/AuthorizeSecurityGroupIngress/RevokeSecurityGroupIngress/"
        "AuthorizeSecurityGroupEgress/RevokeSecurityGroupEgress/CreateTags/DeleteTags + ec2:Describe*",
    ),
    (
        "create_alb_resources=true",
        "ALB, listeners/listener rules, target groups, target registrations.",
        "elasticloadbalancing:Create*/Modify*/Delete*/RegisterTargets/DeregisterTargets/AddTags/RemoveTags + elasticloadbalancing:Describe*",
    ),
    (
        "create_cloudwatch_log_groups=true",
        "Service log groups and retention policy updates.",
        "logs:CreateLogGroup/DeleteLogGroup/PutRetentionPolicy/TagResource/UntagResource + logs:Describe*",
    ),
    (
        "create_ecs_task_roles=true or manage_ecs_task_role_policies=true",
        "ECS task execution/task roles and inline/attached policies.",
        "iam:CreateRole/DeleteRole/AttachRolePolicy/DetachRolePolicy/PutRolePolicy/DeleteRolePolicy/GetRole/PassRole/List*",
    ),
    (
        "create_github_actions_iam=true",
        "GitHub Actions OIDC provider and deploy role policy.",
        "iam:CreateOpenIDConnectProvider/DeleteOpenIDConnectProvider/GetOpenIDConnectProvider/CreateRole/DeleteRole/PutRolePolicy",
    ),
    (
        "create_efs_resources=true and enable_shared_uploads=true",
        "EFS filesystem, access point, mount targets, and EFS SG rules.",
        "elasticfilesystem:Create*/Delete*/Describe*/TagResource/UntagResource/PutLifecycleConfiguration + ec2:Describe*",
    ),
    (
        "create_data_services=true",
        "RDS Postgres instance/subnet group/SG and ElastiCache Redis cluster/subnet group/SG.",
        "rds:Create*/Modify*/Delete*/Describe*/AddTagsToResource/RemoveTagsFromResource + "
        "elasticache:Create*/Modify*/Delete*/Describe*/AddTagsToResource/RemoveTagsFromResource + ec2:Describe*",
    ),
    (
        "ses_domain set (non-empty)",
        "SES domain identity + DKIM resources.",
        "ses:VerifyDomainIdentity/VerifyDomainDkim (modeled via aws_ses_domain_identity/aws_ses_domain_dkim)",
    ),
]


@dataclass(frozen=True)
class ModulePermission:
    file_name: str
    responsibility: str
    toggle: str
    create_actions: str
    reuse_actions: str
    failure_signal: str


MODULE_PERMISSION_BREAKDOWN: list[ModulePermission] = [
    ModulePermission(
        file_name="providers.tf",
        responsibility="Provider/backend wiring for S3 state and DynamoDB lock table.",
        toggle="Always evaluated",
        create_actions="No resource creation in this file.",
        reuse_actions="s3:GetObject/PutObject/ListBucket, dynamodb:GetItem/PutItem/DeleteItem/DescribeTable (state + lock handling).",
        failure_signal="Terraform init/state lock failures before planning.",
    ),
    ModulePermission(
        file_name="variables.tf",
        responsibility="Input contract and validation checks.",
        toggle="Always evaluated",
        create_actions="No AWS API actions.",
        reuse_actions="No AWS API actions.",
        failure_signal="Plan/input validation errors for missing required values or invalid modes.",
    ),
    ModulePermission(
        file_name="vpc.tf",
        responsibility="VPC/subnets/routes/NAT creation OR discovery of pre-existing network assets.",
        toggle="create_networking",
        create_actions="ec2:CreateVpc/DeleteVpc, ec2:CreateSubnet/DeleteSubnet, ec2:CreateRouteTable/CreateRoute/DeleteRouteTable, "
        "ec2:CreateInternetGateway/AttachInternetGateway/DeleteInternetGateway/DetachInternetGateway, ec2:AllocateAddress/ReleaseAddress, "
        "ec2:CreateNatGateway/DeleteNatGateway, ec2:CreateTags/DeleteTags.",
        reuse_actions="ec2:DescribeVpcs, ec2:DescribeSubnets, ec2:DescribeAvailabilityZones, ec2:DescribeRouteTables.",
        failure_signal="AccessDenied on CreateVpc/AllocateAddress or check failure for missing existing VPC/subnets.",
    ),
    ModulePermission(
        file_name="security_groups.tf",
        responsibility="ALB/ECS security groups and ingress/egress rule wiring.",
        toggle="create_service_security_groups",
        create_actions="ec2:CreateSecurityGroup/DeleteSecurityGroup, ec2:AuthorizeSecurityGroupIngress/RevokeSecurityGroupIngress, "
        "ec2:AuthorizeSecurityGroupEgress/RevokeSecurityGroupEgress, ec2:CreateTags/DeleteTags.",
        reuse_actions="ec2:DescribeSecurityGroups.",
        failure_signal="InvalidGroup.Duplicate on SG names or AccessDenied on security group create/rule APIs.",
    ),
    ModulePermission(
        file_name="alb.tf",
        responsibility="ALB, listeners, listener rules, target groups, and resource discovery for reuse mode.",
        toggle="create_alb_resources",
        create_actions="elasticloadbalancing:CreateLoadBalancer/DeleteLoadBalancer/ModifyLoadBalancer, "
        "elasticloadbalancing:CreateTargetGroup/DeleteTargetGroup/ModifyTargetGroup/RegisterTargets/DeregisterTargets, "
        "elasticloadbalancing:CreateListener/DeleteListener/ModifyListener, "
        "elasticloadbalancing:CreateRule/DeleteRule/ModifyRule, elasticloadbalancing:AddTags/RemoveTags.",
        reuse_actions="elasticloadbalancing:DescribeLoadBalancers, elasticloadbalancing:DescribeTargetGroups, elasticloadbalancing:DescribeListeners.",
        failure_signal="TargetGroup already exists / listener rule conflicts when create flags mismatch existing infra.",
    ),
    ModulePermission(
        file_name="cloudwatch.tf",
        responsibility="CloudWatch log groups for ECS services.",
        toggle="create_cloudwatch_log_groups",
        create_actions="logs:CreateLogGroup/DeleteLogGroup/PutRetentionPolicy/TagResource/UntagResource.",
        reuse_actions="logs:DescribeLogGroups.",
        failure_signal="ResourceAlreadyExistsException for log groups when creation is left on for pre-existing groups.",
    ),
    ModulePermission(
        file_name="ecr.tf",
        responsibility="ECR repositories and lifecycle policies.",
        toggle="Always managed",
        create_actions="ecr:CreateRepository/DeleteRepository, ecr:PutLifecyclePolicy/DeleteLifecyclePolicy, ecr:TagResource/UntagResource.",
        reuse_actions="ecr:DescribeRepositories, ecr:DescribeImages, ecr:GetLifecyclePolicy, ecr:ListTagsForResource.",
        failure_signal="Repository already exists unless imported/state-aligned; push/pull issues if repo policy/permissions missing.",
    ),
    ModulePermission(
        file_name="iam.tf",
        responsibility="OIDC provider, deploy role policy, ECS task roles and attached inline policies.",
        toggle="create_github_actions_iam / create_ecs_task_roles / manage_ecs_task_role_policies",
        create_actions="iam:CreateOpenIDConnectProvider/DeleteOpenIDConnectProvider, iam:CreateRole/DeleteRole, "
        "iam:AttachRolePolicy/DetachRolePolicy, iam:PutRolePolicy/DeleteRolePolicy.",
        reuse_actions="iam:GetRole, iam:GetOpenIDConnectProvider, iam:ListRolePolicies, iam:ListAttachedRolePolicies, iam:PassRole.",
        failure_signal="AccessDenied on CreateRole/CreateOpenIDConnectProvider or check failures for missing existing role ARNs.",
    ),
    ModulePermission(
        file_name="efs.tf",
        responsibility="Shared EFS file system, access point, mount targets, and EFS SG.",
        toggle="enable_shared_uploads + create_efs_resources",
        create_actions="elasticfilesystem:CreateFileSystem/DeleteFileSystem, elasticfilesystem:CreateMountTarget/DeleteMountTarget, "
        "elasticfilesystem:CreateAccessPoint/DeleteAccessPoint, elasticfilesystem:TagResource/UntagResource, "
        "elasticfilesystem:PutLifecycleConfiguration, ec2:CreateSecurityGroup/DeleteSecurityGroup, "
        "ec2:AuthorizeSecurityGroupIngress/RevokeSecurityGroupIngress, ec2:AuthorizeSecurityGroupEgress/RevokeSecurityGroupEgress.",
        reuse_actions="elasticfilesystem:DescribeFileSystems/DescribeMountTargets/DescribeAccessPoints.",
        failure_signal="AccessDenied on elasticfilesystem:TagResource or check failure if shared uploads enabled with no EFS IDs.",
    ),
    ModulePermission(
        file_name="rds.tf",
        responsibility="Postgres DB, subnet group, and DB security group.",
        toggle="create_data_services",
        create_actions="rds:CreateDBInstance/DeleteDBInstance/ModifyDBInstance, rds:CreateDBSubnetGroup/DeleteDBSubnetGroup/ModifyDBSubnetGroup, "
        "rds:AddTagsToResource/RemoveTagsFromResource, ec2:CreateSecurityGroup/DeleteSecurityGroup + SG rule actions.",
        reuse_actions="rds:DescribeDBInstances, rds:DescribeDBSubnetGroups, ec2:DescribeSecurityGroups.",
        failure_signal="AccessDenied for RDS create/modify APIs or check failure when db_password missing in create mode.",
    ),
    ModulePermission(
        file_name="elasticache.tf",
        responsibility="Redis cluster, subnet group, and Redis security group.",
        toggle="create_data_services",
        create_actions="elasticache:CreateCacheCluster/DeleteCacheCluster/ModifyCacheCluster, "
        "elasticache:CreateCacheSubnetGroup/DeleteCacheSubnetGroup/ModifyCacheSubnetGroup, "
        "elasticache:AddTagsToResource/RemoveTagsFromResource, ec2:CreateSecurityGroup/DeleteSecurityGroup + SG rule actions.",
        reuse_actions="elasticache:DescribeCacheClusters, elasticache:DescribeCacheSubnetGroups, ec2:DescribeSecurityGroups.",
        failure_signal="AccessDenied on ElastiCache create APIs or SG creation.",
    ),
    ModulePermission(
        file_name="ses.tf",
        responsibility="SES domain identity/DKIM and task-role SES send permissions.",
        toggle="ses_domain + email_provider + manage_task_role_policies",
        create_actions="ses:VerifyDomainIdentity, ses:VerifyDomainDkim, iam:PutRolePolicy/DeleteRolePolicy (SES send policy).",
        reuse_actions="ses:GetIdentityVerificationAttributes, iam:GetRolePolicy.",
        failure_signal="AccessDenied on SES verify APIs or missing IAM rights to attach SES send policy.",
    ),
    ModulePermission(
        file_name="ecs.tf",
        responsibility="ECS cluster, task definitions, and services for backend/frontend/worker/beat.",
        toggle="Always managed",
        create_actions="ecs:CreateCluster/UpdateCluster, ecs:RegisterTaskDefinition/DeregisterTaskDefinition, "
        "ecs:CreateService/UpdateService/DeleteService, ecs:TagResource, iam:PassRole.",
        reuse_actions="ecs:DescribeClusters, ecs:DescribeServices, ecs:ListServices, ecs:DescribeTaskDefinition.",
        failure_signal="Creation of service was not idempotent when service exists outside Terraform state.",
    ),
    ModulePermission(
        file_name="imports.tf",
        responsibility="Initial state imports for existing ECR repositories.",
        toggle="Always evaluated",
        create_actions="No creation actions; import reads existing resources into state.",
        reuse_actions="ecr:DescribeRepositories.",
        failure_signal="Import failures if repo names do not exist or caller cannot read ECR.",
    ),
    ModulePermission(
        file_name="outputs.tf",
        responsibility="Exposes computed IDs/endpoints to operators and automation.",
        toggle="Always evaluated",
        create_actions="No AWS API actions in this file.",
        reuse_actions="No AWS API actions in this file.",
        failure_signal="Output resolution errors when referenced resources are intentionally disabled and not guarded.",
    ),
]


def _list_infra_directories() -> list[str]:
    directories = ["infra"]
    for path in sorted(INFRA_ROOT.rglob("*")):
        if not path.is_dir():
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in IGNORED_PARTS for part in rel_parts):
            continue
        if any(part.startswith(".") for part in rel_parts):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        directories.append(rel)
    return directories


def _list_terraform_files() -> list[str]:
    return sorted(path.name for path in (INFRA_ROOT / "terraform").glob("*.tf"))


def _validate_documented_terraform_files(terraform_files: list[str]) -> None:
    documented_in_modules = {file_name for file_name, _, _ in TF_MODULES}
    documented_in_permissions = {item.file_name for item in MODULE_PERMISSION_BREAKDOWN}
    discovered = set(terraform_files)

    if discovered != documented_in_modules:
        missing = sorted(discovered - documented_in_modules)
        extra = sorted(documented_in_modules - discovered)
        raise ValueError(
            "TF_MODULES drift detected in check_infra_inventory.py. "
            f"Missing entries: {missing} | Extra entries: {extra}"
        )

    if discovered != documented_in_permissions:
        missing = sorted(discovered - documented_in_permissions)
        extra = sorted(documented_in_permissions - discovered)
        raise ValueError(
            "MODULE_PERMISSION_BREAKDOWN drift detected in check_infra_inventory.py. "
            f"Missing entries: {missing} | Extra entries: {extra}"
        )


def _render_markdown(directories: list[str]) -> str:
    unknown_directories = [directory for directory in directories if directory not in FOLDER_DETAILS]
    if unknown_directories:
        joined = ", ".join(unknown_directories)
        raise ValueError(
            "Undocumented infra directories found. Add them to FOLDER_DETAILS in "
            f"infra/scripts/check_infra_inventory.py: {joined}"
        )

    lines: list[str] = []
    lines.append("# Infra Inventory and Permissions")
    lines.append("")
    lines.append("Generated by `python3 infra/scripts/check_infra_inventory.py`.")
    lines.append("Run with `--check` in CI to fail builds when this inventory drifts.")
    lines.append("")
    lines.append("## Existing Folders")
    lines.append("")
    lines.append("| Folder | What it does | Permission impact |")
    lines.append("|---|---|---|")
    for directory in directories:
        what_it_does, permission_impact = FOLDER_DETAILS[directory]
        lines.append(f"| `{directory}` | {what_it_does} | {permission_impact} |")

    lines.append("")
    lines.append("## Terraform Modules")
    lines.append("")
    lines.append("| File | Responsibility | Main Toggle/Mode |")
    lines.append("|---|---|---|")
    for file_name, responsibility, toggle in TF_MODULES:
        lines.append(f"| `infra/terraform/{file_name}` | {responsibility} | `{toggle}` |")

    lines.append("")
    lines.append("## AWS IAM Permissions Required by Deploy Role")
    lines.append("")
    lines.append("| Scope | Used for | Required action families |")
    lines.append("|---|---|---|")
    for scope, used_for, permissions in PERMISSION_MATRIX:
        lines.append(f"| `{scope}` | {used_for} | `{permissions}` |")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- If `create_*` flags are `false`, Terraform primarily needs read/discovery permissions plus ECS/ECR deploy permissions.")
    lines.append("- If a flag is `true`, ensure the deploy role has corresponding create/update/delete permissions before running `terraform apply`.")
    lines.append("- Existing-resource reuse depends on names/tags in Terraform data sources (VPC/subnets/SGs/ALB/target groups/IAM roles).")
    lines.append("- For per-module action-level mapping, see `infra/TERRAFORM_PERMISSION_MAP.md`.")
    lines.append("")

    return "\n".join(lines)


def _render_permission_map(terraform_files: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Terraform Permission Map")
    lines.append("")
    lines.append("Generated by `python3 infra/scripts/check_infra_inventory.py`.")
    lines.append("This file is designed for deploy-role policy reviews before sandbox/production builds.")
    lines.append("")
    lines.append("## How To Use")
    lines.append("")
    lines.append("1. Pick your deploy mode (`bootstrap` vs `reuse existing`).")
    lines.append("2. Match enabled `create_*` toggles to rows below.")
    lines.append("3. Ensure the CI/deploy role has every required action family for enabled rows.")
    lines.append("4. Keep unused create flags off to avoid unnecessary privileges and duplicate-resource failures.")
    lines.append("")
    lines.append("## Mode Profiles")
    lines.append("")
    lines.append("- `Sandbox bootstrap`: typically enables `create_networking`, `create_service_security_groups`, `create_alb_resources`, `create_ecs_task_roles`, `create_cloudwatch_log_groups`, `create_data_services`, and `create_efs_resources`.")
    lines.append("- `Production reuse`: typically disables most `create_*` flags and provides explicit `existing_*` IDs/ARNs; requires mostly read/discovery + ECS/ECR deploy permissions.")
    lines.append("")
    lines.append("## Module-by-Module AWS API Families")
    lines.append("")
    lines.append("| File | Responsibility | Toggle/Mode | Create/Mutate action families | Reuse/discovery action families | Typical failure signal |")
    lines.append("|---|---|---|---|---|---|")
    items_by_file = {item.file_name: item for item in MODULE_PERMISSION_BREAKDOWN}
    for file_name in terraform_files:
        item = items_by_file[file_name]
        lines.append(
            f"| `infra/terraform/{item.file_name}` | {item.responsibility} | `{item.toggle}` | "
            f"`{item.create_actions}` | `{item.reuse_actions}` | {item.failure_signal} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- These are practical action families for this stack; exact resource-level scoping can be tightened in your IAM policy implementation.")
    lines.append("- If Terraform reports `already exists`, either import the resource into state or disable creation and provide `existing_*` inputs.")
    lines.append("- If Terraform reports `AccessDenied`, compare the failing API action to this map and add the missing permission for the active mode.")
    lines.append("")
    return "\n".join(lines)


def _write_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify infra inventory and Terraform permission documentation."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated infra docs are out of date.",
    )
    args = parser.parse_args()

    directories = _list_infra_directories()
    terraform_files = _list_terraform_files()
    try:
        _validate_documented_terraform_files(terraform_files)
        inventory_content = _render_markdown(directories)
        permission_map_content = _render_permission_map(terraform_files)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.check:
        current_inventory = (
            OUTPUT_INVENTORY_PATH.read_text(encoding="utf-8")
            if OUTPUT_INVENTORY_PATH.exists()
            else ""
        )
        current_permission_map = (
            OUTPUT_PERMISSION_MAP_PATH.read_text(encoding="utf-8")
            if OUTPUT_PERMISSION_MAP_PATH.exists()
            else ""
        )
        if current_inventory != inventory_content:
            print(
                "infra/INFRA_INVENTORY.md is out of date. Run "
                "`python3 infra/scripts/check_infra_inventory.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        if current_permission_map != permission_map_content:
            print(
                "infra/TERRAFORM_PERMISSION_MAP.md is out of date. Run "
                "`python3 infra/scripts/check_infra_inventory.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print("Infra documentation checks passed.")
        return 0

    changed_inventory = _write_if_changed(OUTPUT_INVENTORY_PATH, inventory_content)
    changed_permission_map = _write_if_changed(OUTPUT_PERMISSION_MAP_PATH, permission_map_content)
    messages = []
    messages.append(
        "Wrote infra/INFRA_INVENTORY.md."
        if changed_inventory
        else "infra/INFRA_INVENTORY.md already up to date."
    )
    messages.append(
        "Wrote infra/TERRAFORM_PERMISSION_MAP.md."
        if changed_permission_map
        else "infra/TERRAFORM_PERMISSION_MAP.md already up to date."
    )
    print(" ".join(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
