# Deployment Guide

This guide describes the deployment flow for the CloudFormation stack, Grafana assets, and GitHub Actions automation in this repository.

## Prerequisites

- One AWS account for the assessment.
- AWS CLI v2 configured locally for bootstrap work.
- IAM Identity Center enabled in the deployment region.
- GitHub repository with Actions enabled.
- GitHub OIDC IAM role for deployments.
- AWS Managed Grafana available in the selected region.
- A confirmed Grafana 12.x version for the workspace. This repository defaults to `12.4`.

Verify available Grafana versions:

```bash
aws grafana list-versions --region us-east-1
```

## Required GitHub Variables

Use repository or environment variables:

```text
AWS_REGION=us-east-1
AWS_ROLE_ARN=arn:aws:iam::<account-id>:role/github-observability-deploy
STACK_NAME=solvex-observability
PARAMETER_FILE=infra/parameters/dev.json
```

Do not store long-lived AWS access keys in GitHub.

## Optional GitHub Secrets

Prefer generating Grafana service account tokens at runtime. If the implementation stores a token temporarily, use:

```text
GRAFANA_TOKEN=<short-lived-token>
```

Amazon Managed Grafana service account tokens should be rotated frequently and can be generated with a maximum TTL of 30 days.

## Local Platform Deployment

Validate the template:

```bash
aws cloudformation validate-template \
  --template-body file://infra/main.yaml
```

Deploy the platform:

```bash
PARAMETER_OVERRIDES="$(
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(" ".join(f"{k}={v}" for k,v in d.items()))' infra/parameters/dev.json
)"

aws cloudformation deploy \
  --stack-name solvex-observability \
  --template-file infra/main.yaml \
  --parameter-overrides $PARAMETER_OVERRIDES \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

Read outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name solvex-observability \
  --query "Stacks[0].Outputs" \
  --output table
```

Expected outputs:

```text
WorkspaceId
WorkspaceEndpoint
WorkspaceStatus
SnsTopicArn
CloudWatchDashboardName
GrafanaWorkspaceRoleArn
```

## SSO Bootstrap

After the workspace is active:

1. Open the Amazon Managed Grafana console.
2. Select the workspace.
3. Assign IAM Identity Center users/groups.
4. Grant at least one admin user.
5. Log in once and confirm the workspace is reachable.

If identity assignment is automated later, keep it separate from core infrastructure so reviewer-owned group IDs can be passed safely as parameters.

## Grafana Asset Deployment

The GitHub workflow should perform this sequence after CloudFormation succeeds:

```bash
GRAFANA_TOKEN="$(scripts/ensure-service-account-token.sh --workspace-id "$WORKSPACE_ID" --region "$AWS_REGION")"

scripts/deploy-grafana-assets.py \
  --endpoint "$GRAFANA_ENDPOINT" \
  --token "$GRAFANA_TOKEN" \
  --sns-topic-arn "$SNS_TOPIC_ARN" \
  --region "$AWS_REGION"
```

The deployment script should apply:

1. Folders.
2. CloudWatch data source.
3. Dashboards.
4. Notification templates.
5. SNS contact point.
6. Notification policy tree.
7. Alert rule groups.

## Smoke Tests

Run the smoke test script after platform and Grafana asset deployment:

```bash
scripts/smoke-test.py \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --token "$GRAFANA_TOKEN" \
  --require-grafana-assets
```

The script reads CloudFormation outputs when `--stack-name` is provided, then checks:

- CloudFormation stack status.
- AWS Managed Grafana workspace status.
- CloudWatch dashboard existence.
- SNS topic existence.
- Grafana `/api/health`.
- CloudWatch data source.
- Grafana dashboards.
- Grafana contact points, notification templates, and alert rules.

Minimum manual checks:

```bash
curl -fsS "$GRAFANA_ENDPOINT/api/health"
curl -fsS \
  -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_ENDPOINT/api/datasources"
```

Manual checks:

- CloudWatch data source test succeeds.
- CloudWatch dashboard exists in AWS console.
- Grafana dashboard panels render data.
- SNS contact point test publishes a message.
- Alert rules show healthy evaluation status.

## Rollback

For bad dashboard or alert changes:

1. Revert the dashboard/alert JSON commit.
2. Re-run the GitHub workflow.
3. If notifications are noisy, temporarily mute the route or disable the affected rule group.

For infrastructure rollback:

```bash
PARAMETER_OVERRIDES="$(
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(" ".join(f"{k}={v}" for k,v in d.items()))' infra/parameters/dev.json
)"

aws cloudformation deploy \
  --stack-name solvex-observability \
  --template-file infra/main.yaml \
  --parameter-overrides $PARAMETER_OVERRIDES \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

CloudFormation should converge the platform back to the desired state.

## Teardown

```bash
aws cloudformation delete-stack \
  --stack-name solvex-observability \
  --region us-east-1
```

Then confirm:

- Grafana workspace is deleted.
- SNS topic and subscriptions are deleted.
- CloudWatch dashboard is deleted.
- Custom resource Lambda log group is retained or deleted according to the retention policy.
