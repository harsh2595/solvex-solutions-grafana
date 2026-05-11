# Scripts

This directory contains automation used by local operators and GitHub Actions.

## Scripts

```text
scripts/
|-- deploy-grafana-assets.py
|-- ensure-service-account-token.sh
|-- smoke-test.py
`-- validate-json.sh
```

## Responsibilities

- `ensure-service-account-token.sh`: creates or locates a Grafana service account and mints a short-lived token through AWS Managed Grafana APIs.
- `deploy-grafana-assets.py`: applies folders, data sources, dashboards, notification templates, contact points, policies, and alert rules.
- `smoke-test.py`: validates stack outputs, AWS Managed Grafana health, CloudWatch dashboard, SNS topic, data source, dashboards, contact points, templates, and alert rules.
- `validate-json.sh`: checks dashboard and alert JSON before deployment.

Scripts should be idempotent so repeated GitHub Actions runs converge the same desired state.

## Smoke Test Example

```bash
scripts/smoke-test.py \
  --stack-name solvex-observability \
  --region us-east-1 \
  --token "$GRAFANA_TOKEN" \
  --require-grafana-assets
```
