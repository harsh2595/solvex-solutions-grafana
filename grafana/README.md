# Grafana Assets

This directory contains versioned Grafana content deployed by GitHub Actions or `scripts/deploy-grafana-assets.py`.

## Files

```text
grafana/
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

## Dashboard Standards

- Stable dashboard UIDs.
- Folder ownership by platform/service team.
- Variables for region, namespace, service, and environment.
- Panels grouped by golden signals: traffic, errors, latency, saturation.
- Links to CloudWatch logs and runbooks.

## Alert Standards

- Every alert has `severity`, `team`, `service`, and `environment` labels.
- Every alert has a runbook link.
- Use `for` durations to reduce flapping.
- Use no-data handling intentionally.
- Route through notification policies instead of hard-coding contact points in every rule.
