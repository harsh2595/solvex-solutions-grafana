# File Structure

This repository is organized so infrastructure, Grafana content, automation, and operational documentation have clear ownership.

## Documentation

```text
docs/
|-- architecture.md
|-- assessment-checklist.md
|-- deployment-guide.md
|-- file-structure.md
|-- diagrams/
|   `-- architecture.mmd
`-- runbooks/
    `-- alert-response.md
```

- `architecture.md`: design decisions and component responsibilities.
- `deployment-guide.md`: local and CI deployment flow.
- `assessment-checklist.md`: requirement-to-evidence mapping for the reviewer.
- `diagrams/architecture.mmd`: reusable Mermaid diagram source.
- `runbooks/alert-response.md`: starter incident response runbook.

## Infrastructure

```text
infra/
|-- README.md
|-- main.yaml
|-- parameters/
|   `-- dev.json
`-- custom-resources/
    `-- plugin-installer/
        |-- app.py
        `-- requirements.txt
```

- `main.yaml`: CloudFormation entry point for AWS Managed Grafana, IAM, SNS, CloudWatch dashboard, and custom resource Lambda.
- `parameters/dev.json`: single-account assessment parameters.
- `custom-resources/plugin-installer`: Lambda code that installs approved Grafana plugins through the Grafana API.

## Grafana Content

```text
grafana/
|-- README.md
|-- dashboards/
|   |-- cloudwatch-account-overview.json
|   `-- workload-health.json
|-- alerts/
|   |-- contact-points.json
|   |-- notification-policies.json
|   |-- notification-templates.json
|   `-- rule-groups.json
`-- provisioning/
    |-- folders.json
    `-- datasources.json
```

- `dashboards`: versioned dashboard JSON.
- `alerts`: Grafana Alerting resources.
- `provisioning`: folders and CloudWatch data source configuration.

## Automation

```text
scripts/
|-- README.md
|-- deploy-grafana-assets.py
|-- ensure-service-account-token.sh
|-- smoke-test.py
`-- validate-json.sh
```

- `ensure-service-account-token.sh`: creates or finds a Grafana service account and mints a short-lived token.
- `deploy-grafana-assets.py`: applies Grafana content idempotently.
- `smoke-test.py`: runs post-deployment AWS and Grafana API checks.
- `validate-json.sh`: validates JSON before deployment.

## CI/CD

```text
.github/
`-- workflows/
    |-- README.md
    |-- deploy-observability.yml
    `-- smoke-test.yml
```

- `deploy-observability.yml`: GitHub Actions workflow for validation, CloudFormation deployment, and Grafana content deployment.
- `smoke-test.yml`: manually triggered or reusable workflow that runs post-deployment smoke checks.
