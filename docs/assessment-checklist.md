# Assessment Checklist

Use this checklist to explain the solution during review.

## Requirement Coverage

| Requirement | Evidence to show |
| --- | --- |
| AWS Managed Grafana created by code | CloudFormation stack contains `AWS::Grafana::Workspace`. |
| SSO integration | Workspace uses `AuthenticationProviders: [AWS_SSO]`; IAM Identity Center assignment procedure is documented. |
| Plugins installed through code | Custom resource Lambda installs allowlisted plugins through the Grafana plugin API. |
| CloudWatch observability | `grafana/provisioning/datasources.json`, native CloudWatch dashboard, and Grafana dashboards exist. |
| Custom CloudWatch dashboard | `AWS::CloudWatch::Dashboard` uses a JSON dashboard body. |
| Grafana alerts to SNS | `grafana/alerts/contact-points.json` creates a contact point type `sns`; workspace role can publish to the SNS topic. |
| Notification templates | `grafana/alerts/notification-templates.json` is deployed before policies/rules. |
| Automatic deployment after setup | `.github/workflows/deploy-observability.yml` deploys Grafana assets after CloudFormation outputs are available. |
| Single AWS account | Workspace, CloudWatch, SNS, IAM roles, and Lambda custom resource are all in one account. |
| Clean documentation | README, architecture, deployment guide, runbook, and repo structure are present. |

## Design Talking Points

- CloudFormation owns AWS infrastructure; Grafana APIs own Grafana content.
- GitHub OIDC avoids static AWS credentials.
- Short-lived service account tokens reduce secret lifetime.
- Plugin allowlist controls supply-chain risk.
- Customer-managed IAM makes permissions reviewable.
- Alert labels and templates improve routing and incident response.
- Dashboards are versioned JSON, so changes are peer-reviewable.

## Demo Path

1. Show the architecture diagram.
2. Open CloudFormation stack resources.
3. Show the AWS Managed Grafana workspace and SSO configuration.
4. Show the CloudWatch dashboard.
5. Show the Grafana CloudWatch data source.
6. Open the Grafana dashboard.
7. Show alert rule, notification template, and SNS contact point.
8. Open GitHub Actions run proving automatic deployment.
9. Trigger or test SNS notification.
10. Walk through the runbook link from the alert.

## Common Reviewer Questions

| Question | Suggested answer |
| --- | --- |
| Why not put dashboards in CloudFormation? | Dashboard and alert JSON changes are application content. Keeping them outside CloudFormation makes reviews, diffs, and rollbacks cleaner. |
| How are plugins controlled? | The custom resource accepts an allowlist and optional versions. It should reject unknown plugin IDs. |
| How do you avoid noisy alerts? | Use warning/critical thresholds, `for` durations, no-data policy, grouping labels, and burn-rate style rules where applicable. |
| How do you secure Grafana API access? | Use service accounts, short-lived tokens, GitHub OIDC, no committed secrets, and least-privilege role permissions. |
| How do you support multiple environments later? | Parameter files and GitHub environments can separate dev/stage/prod while reusing the same templates and asset deployer. |
