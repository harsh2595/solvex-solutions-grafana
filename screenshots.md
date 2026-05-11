# Screenshot Evidence

This root-level index lists the screenshots captured for the deployed AWS Managed Grafana observability platform.

Detailed screenshot gallery: [screenshots/screenshots.md](screenshots/screenshots.md)

## Evidence Summary

| Evidence | Screenshot | What it proves |
| --- | --- | --- |
| GitHub Actions variables/secrets | [github_actions_secrets.png](screenshots/github_actions_secrets.png) | Required GitHub Actions configuration is present for OIDC deployment. |
| GitHub Actions pipeline success | [pipeline builds successfully.png](<screenshots/pipeline builds successfully.png>) | Validation, platform deployment, Grafana asset deployment, and smoke tests completed successfully. |
| CloudFormation stack completed | [cloudformation_stack_completed.png](screenshots/cloudformation_stack_completed.png) | Infrastructure stack reached a successful completed state. |
| CloudFormation resources created | [cloudformation stack is up.png](<screenshots/cloudformation stack is up.png>) | Stack-managed AWS resources were created under one stack. |
| Amazon Managed Grafana workspace | [aws grafana is up.png](<screenshots/aws grafana is up.png>) | Managed Grafana workspace is available. |
| Grafana workspace URL | [awsgrafana_url.png](screenshots/awsgrafana_url.png) | Workspace can be opened through the generated endpoint. |
| Grafana dashboards folder | [dashboard_grafana.png](screenshots/dashboard_grafana.png) | `CloudWatch Account Overview` dashboard is deployed. |
| Workload dashboard | [workload health.png](<screenshots/workload health.png>) | `Workload Health` dashboard is deployed. |
| SNS contact point | [contact point.png](<screenshots/contact point.png>) | Grafana alerting is configured to send notifications to AWS SNS. |
| Notification policies | [notification policies.png](<screenshots/notification policies.png>) | Grafana notification routing is configured. |
| SNS subscription confirmed | [sns_subscription confirmed.png](<screenshots/sns_subscription confirmed.png>) | SNS alert delivery target is confirmed. |
| IAM Identity Center user | [iam user.png](<screenshots/iam user.png>) | User access was configured for Grafana login. |

## Notes

- Dashboard panels can show `No data` in a quiet AWS account. That is acceptable when the dashboard loads and the CloudWatch data source has no permission errors.
- Screenshots are assessment evidence, not secrets. Avoid committing screenshots that expose private emails, account IDs, tokens, or sensitive resource names.
