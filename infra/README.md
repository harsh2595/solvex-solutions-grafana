# Infrastructure

This directory contains CloudFormation for the assessment.

## Files

```text
infra/
|-- main.yaml
|-- parameters/
|   `-- dev.json
`-- custom-resources/
    `-- plugin-installer/
        |-- app.py
        `-- requirements.txt
```

## CloudFormation Resources

- `AWS::IAM::Role` for AWS Managed Grafana workspace access.
- `AWS::Grafana::Workspace`.
- `AWS::SNS::Topic`.
- `AWS::CloudWatch::Dashboard`.
- `AWS::Lambda::Function` for plugin installation.
- `AWS::IAM::Role` for the custom resource Lambda.
- `Custom::GrafanaPlugins` custom resource.

The Lambda source is also kept in `custom-resources/plugin-installer/app.py` for review. The deployable CloudFormation template uses inline Lambda code so the stack can be deployed without a packaging bucket.

## Key Parameters

```text
EnvironmentName
GrafanaWorkspaceName
GrafanaVersion
AllowedPluginIds
SnsSubscriptionEmail
CloudWatchDashboardName
```

Keep account-specific values as parameters because they vary by AWS account and assessment environment.
