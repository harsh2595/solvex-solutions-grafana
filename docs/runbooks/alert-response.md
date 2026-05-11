# Alert Response Runbook

Use this starter runbook for all Grafana alerts until service-specific runbooks are added.

## Triage

1. Open the alert notification and identify:
   - `service`
   - `environment`
   - `severity`
   - `dashboard_url`
   - `runbook_url`
2. Open the linked Grafana dashboard.
3. Check whether the alert is isolated to one service or affecting multiple services.
4. Check CloudWatch metrics for the same time window.
5. Check recent deployments, scaling events, and AWS service health.

## CloudWatch Checks

Useful AWS CLI patterns:

```bash
aws cloudwatch describe-alarms --state-value ALARM
```

```bash
aws logs describe-log-groups
```

```bash
aws cloudwatch list-metrics --namespace AWS/Lambda
```

Adjust namespace and dimensions for the affected workload.

## Grafana Checks

- Confirm data source health.
- Inspect panel query and time range.
- Compare current window with previous healthy window.
- Check whether alert state is `Alerting`, `Pending`, `NoData`, or `Error`.
- Review annotations for recent deploys if annotations are enabled.

## Mitigation

Choose the least risky mitigation available:

- Roll back the latest application deployment.
- Scale out the affected service.
- Disable or drain unhealthy targets.
- Increase queue consumers.
- Restore dependency availability.
- Escalate to the owning team if the issue is outside platform control.

## Escalation

Escalate when:

- Customer-facing impact is confirmed.
- Severity is critical and no owner acknowledges within the expected window.
- Multiple services or regions are affected.
- The alert is caused by infrastructure shared across teams.

Escalation targets:

- Platform on-call
- Service owner
- Incident commander
- Cloud/network team when AWS networking or IAM is involved

## Post-Incident Follow-Up

After resolution:

- Add incident timeline.
- Confirm the alert fired at the right time.
- Record whether the threshold was too sensitive or too slow.
- Add missing dashboard panels.
- Add or update the service-specific runbook.
- Create follow-up work for automation gaps.
