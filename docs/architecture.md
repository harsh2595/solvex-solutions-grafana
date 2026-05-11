# Architecture

This design builds a single-account observability platform that is intentionally small enough for an assessment, but structured like a production platform.

## Components

| Component | Responsibility |
| --- | --- |
| AWS Managed Grafana | Managed Grafana workspace for dashboards, CloudWatch data source, and Grafana-managed alerting. |
| IAM Identity Center | SSO authentication for workspace users through the `AWS_SSO` provider. |
| CloudWatch | Metrics, logs, alarms, and the native CloudWatch dashboard. |
| SNS | Notification target for Grafana alerts. Subscribers can be email, ChatOps bridge, or incident tooling. |
| CloudFormation | Owns platform infrastructure: workspace, roles, SNS, CloudWatch dashboard, Lambda custom resource. |
| Custom resource Lambda | Installs approved Grafana plugins after the workspace becomes active. |
| GitHub Actions | Deploys infrastructure and then applies Grafana dashboards and alerting assets. |

## Why Customer-Managed Permissions

`PermissionType: CUSTOMER_MANAGED` makes the assessment easier to review because the workspace role, managed policies, and SNS publish permission are explicit in CloudFormation. It also matches production expectations where platform teams control least-privilege IAM instead of relying on console-created service roles.

The workspace role should include:

- `AmazonGrafanaCloudWatchAccess` for CloudWatch metrics/log queries and resource discovery.
- `sns:Publish` scoped to the assessment SNS topic.
- Optional read permissions for additional AWS data sources only when they are actually used.

## SSO Flow

CloudFormation configures the Grafana workspace with `AuthenticationProviders: [AWS_SSO]`. IAM Identity Center itself must be enabled before stack deployment.

The implementation should document the identity bootstrap clearly:

1. Create or identify IAM Identity Center groups such as `grafana-admins`, `grafana-editors`, and `grafana-viewers`.
2. Assign those users/groups to the Amazon Managed Grafana workspace.
3. Validate that at least one admin user can log in before CI deploys dashboards and alerts.

## Plugin Installation Flow

CloudFormation cannot directly install third-party Grafana plugins by itself, so the design uses a custom resource:

1. `AWS::Grafana::Workspace` enables `PluginAdminEnabled: true`.
2. Custom resource Lambda receives workspace ID, endpoint, plugin allowlist, and optional versions.
3. Lambda waits until the workspace status is `ACTIVE`.
4. Lambda creates or uses a short-lived service account token.
5. Lambda calls `POST /api/plugins/:id/install` for each allowlisted plugin.
6. Lambda returns installed plugin IDs and versions in the custom resource response.

The custom resource should be idempotent. Re-running the stack should converge to the desired plugin set instead of failing because a plugin already exists.

## Observability Data Flow

Cloud workloads publish metrics and logs into CloudWatch. AWS Managed Grafana queries CloudWatch through the workspace role. The same signal is shown in two places:

- CloudWatch dashboard: native AWS view for account operators.
- Grafana dashboards: role-based and service-focused views for application and platform users.

The starter implementation should use CloudWatch metrics that exist in most accounts, then make workload-specific namespaces configurable:

- `AWS/Lambda`
- `AWS/ApplicationELB`
- `AWS/ApiGateway`
- `AWS/ECS` or `ContainerInsights`
- `AWS/EKS` where available
- `AWS/Usage`

## Alert Flow

Grafana Alerting owns alert rules and notification policy routing. SNS is configured as the contact point.

Recommended alerting objects:

- Contact point: `sns-platform-alerts`
- Notification template group: `platform-observability`
- Policy tree: route by `severity`, `team`, and `environment`
- Rule groups: one group per service or signal family

Alerts should link back to a dashboard and runbook. That is the difference between an alert that wakes someone up and an alert that helps them fix the issue.

## Automation Boundary

CloudFormation should own AWS infrastructure. Grafana HTTP APIs should own Grafana content.

This split avoids forcing dashboard JSON into CloudFormation templates and makes dashboard/alert changes reviewable as normal source files.
