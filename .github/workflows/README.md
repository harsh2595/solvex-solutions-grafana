# GitHub Actions

This directory contains the deployment and smoke-test workflows.

## Workflows

```text
.github/workflows/deploy-observability.yml
.github/workflows/smoke-test.yml
```

## Jobs

1. `validate`
   - Validate CloudFormation.
   - Validate JSON assets.

2. `deploy-platform`
   - Assume AWS role through GitHub OIDC.
   - Deploy CloudFormation.
   - Export stack outputs.

3. `deploy-grafana-assets`
   - Create short-lived Grafana token.
   - Deploy data source, dashboards, alert templates, contact points, policies, and rules.
   - Run smoke tests.

4. `smoke-test`
   - Can be triggered manually or called by the deployment workflow.
   - Assumes the AWS deploy role through GitHub OIDC.
   - Runs `scripts/smoke-test.py` against the deployed stack and Grafana endpoint.

## Security

- Use GitHub environments for manual approval on protected branches.
- Scope OIDC trust to this repository and branch.
- Do not persist Grafana tokens beyond the workflow run unless a short assessment demo requires it.
