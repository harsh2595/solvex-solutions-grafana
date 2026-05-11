#!/usr/bin/env python3
"""Smoke tests for the AWS Managed Grafana observability platform.

The script is intentionally dependency-light. It uses the AWS CLI for AWS checks
and Python's standard library for Grafana HTTP checks.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


STACK_OUTPUT_KEYS = {
    "WorkspaceId": "workspace_id",
    "WorkspaceEndpoint": "grafana_endpoint",
    "SnsTopicArn": "sns_topic_arn",
    "CloudWatchDashboardName": "cloudwatch_dashboard_name",
}


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


class SmokeTest:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def pass_(self, name: str, detail: str) -> None:
        self.results.append(CheckResult(name, "PASS", detail))
        print(f"[PASS] {name}: {detail}")

    def fail(self, name: str, detail: str) -> None:
        self.results.append(CheckResult(name, "FAIL", detail))
        print(f"[FAIL] {name}: {detail}")

    def skip(self, name: str, detail: str) -> None:
        self.results.append(CheckResult(name, "SKIP", detail))
        print(f"[SKIP] {name}: {detail}")

    def failed(self) -> bool:
        return any(result.status == "FAIL" for result in self.results)

    def summary(self) -> None:
        totals = {"PASS": 0, "FAIL": 0, "SKIP": 0}
        for result in self.results:
            totals[result.status] += 1
        print()
        print(
            "Summary: "
            f"{totals['PASS']} passed, {totals['FAIL']} failed, {totals['SKIP']} skipped"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run post-deployment smoke tests for AWS Managed Grafana."
    )
    parser.add_argument("--stack-name", default=os.getenv("STACK_NAME"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--workspace-id", default=os.getenv("WORKSPACE_ID"))
    parser.add_argument(
        "--endpoint",
        dest="grafana_endpoint",
        default=os.getenv("GRAFANA_ENDPOINT"),
    )
    parser.add_argument("--token", default=os.getenv("GRAFANA_TOKEN"))
    parser.add_argument("--sns-topic-arn", default=os.getenv("SNS_TOPIC_ARN"))
    parser.add_argument(
        "--cloudwatch-dashboard-name",
        default=os.getenv("CLOUDWATCH_DASHBOARD_NAME"),
    )
    parser.add_argument(
        "--require-grafana-assets",
        action="store_true",
        help="Fail when dashboards, contact points, templates, or alert rules are missing.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("SMOKE_TEST_TIMEOUT_SECONDS", "10")),
    )
    return parser.parse_args()


def run_aws(
    service_args: list[str], region: str, check_name: str, tests: SmokeTest
) -> dict[str, Any] | None:
    if not shutil.which("aws"):
        tests.fail(check_name, "aws CLI is not installed or not on PATH")
        return None

    command = ["aws", *service_args, "--region", region, "--output", "json"]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        tests.fail(check_name, stderr)
        return None

    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        tests.fail(check_name, f"invalid JSON response from AWS CLI: {exc}")
        return None


def normalize_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    endpoint = endpoint.strip().rstrip("/")
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    return f"https://{endpoint}"


def http_get(
    endpoint: str,
    path: str,
    token: str | None,
    timeout_seconds: int,
) -> tuple[int, Any]:
    url = urllib.parse.urljoin(f"{endpoint}/", path.lstrip("/"))
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            if not body:
                return response.status, None
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


def load_stack_outputs(args: argparse.Namespace, tests: SmokeTest) -> None:
    if not args.stack_name:
        tests.skip("cloudformation stack", "STACK_NAME or --stack-name was not provided")
        return

    data = run_aws(
        ["cloudformation", "describe-stacks", "--stack-name", args.stack_name],
        args.region,
        "cloudformation stack",
        tests,
    )
    if not data:
        return

    stacks = data.get("Stacks", [])
    if not stacks:
        tests.fail("cloudformation stack", f"stack {args.stack_name} was not found")
        return

    stack = stacks[0]
    status = stack.get("StackStatus", "UNKNOWN")
    if status.endswith("_COMPLETE") and "ROLLBACK" not in status:
        tests.pass_("cloudformation stack", f"{args.stack_name} is {status}")
    else:
        tests.fail("cloudformation stack", f"{args.stack_name} is {status}")

    outputs = {
        item.get("OutputKey"): item.get("OutputValue")
        for item in stack.get("Outputs", [])
        if item.get("OutputKey")
    }
    for output_key, arg_name in STACK_OUTPUT_KEYS.items():
        if getattr(args, arg_name):
            continue
        value = outputs.get(output_key)
        if value:
            setattr(args, arg_name, value)


def check_workspace(args: argparse.Namespace, tests: SmokeTest) -> None:
    if not args.workspace_id:
        tests.skip("grafana workspace", "WORKSPACE_ID or WorkspaceId stack output missing")
        return

    data = run_aws(
        ["grafana", "describe-workspace", "--workspace-id", args.workspace_id],
        args.region,
        "grafana workspace",
        tests,
    )
    if not data:
        return

    workspace = data.get("workspace", {})
    status = workspace.get("status", "UNKNOWN")
    version = workspace.get("grafanaVersion", "unknown")
    endpoint = workspace.get("endpoint")
    if not args.grafana_endpoint and endpoint:
        args.grafana_endpoint = endpoint

    if status == "ACTIVE":
        tests.pass_("grafana workspace", f"{args.workspace_id} is ACTIVE on Grafana {version}")
    else:
        tests.fail("grafana workspace", f"{args.workspace_id} is {status}")


def check_cloudwatch_dashboard(args: argparse.Namespace, tests: SmokeTest) -> None:
    if not args.cloudwatch_dashboard_name:
        tests.skip(
            "cloudwatch dashboard",
            "CLOUDWATCH_DASHBOARD_NAME or CloudWatchDashboardName output missing",
        )
        return

    data = run_aws(
        [
            "cloudwatch",
            "get-dashboard",
            "--dashboard-name",
            args.cloudwatch_dashboard_name,
        ],
        args.region,
        "cloudwatch dashboard",
        tests,
    )
    if not data:
        return

    body = data.get("DashboardBody")
    if not body:
        tests.fail("cloudwatch dashboard", "dashboard exists but has an empty body")
        return

    tests.pass_("cloudwatch dashboard", f"{args.cloudwatch_dashboard_name} exists")


def check_sns_topic(args: argparse.Namespace, tests: SmokeTest) -> None:
    if not args.sns_topic_arn:
        tests.skip("sns topic", "SNS_TOPIC_ARN or SnsTopicArn stack output missing")
        return

    data = run_aws(
        ["sns", "get-topic-attributes", "--topic-arn", args.sns_topic_arn],
        args.region,
        "sns topic",
        tests,
    )
    if not data:
        return

    display_name = data.get("Attributes", {}).get("DisplayName", "")
    suffix = f" display name={display_name}" if display_name else ""
    tests.pass_("sns topic", f"{args.sns_topic_arn} exists{suffix}")


def check_grafana_health(args: argparse.Namespace, tests: SmokeTest) -> None:
    endpoint = normalize_endpoint(args.grafana_endpoint)
    if not endpoint:
        tests.skip("grafana health", "GRAFANA_ENDPOINT or WorkspaceEndpoint output missing")
        return

    try:
        status, body = http_get(endpoint, "/api/health", None, args.timeout_seconds)
    except RuntimeError as exc:
        tests.fail("grafana health", str(exc))
        return

    database_status = ""
    if isinstance(body, dict) and body.get("database"):
        database_status = f", database={body['database']}"
    tests.pass_("grafana health", f"HTTP {status}{database_status}")


def require_token(
    args: argparse.Namespace,
    tests: SmokeTest,
    check_name: str,
    required: bool = False,
) -> bool:
    if args.token:
        return True
    message = "GRAFANA_TOKEN or --token was not provided"
    if required:
        tests.fail(check_name, message)
    else:
        tests.skip(check_name, message)
    return False


def check_grafana_datasources(args: argparse.Namespace, tests: SmokeTest) -> None:
    endpoint = normalize_endpoint(args.grafana_endpoint)
    if not endpoint:
        tests.skip("grafana data sources", "GRAFANA_ENDPOINT or WorkspaceEndpoint output missing")
        return
    if not require_token(args, tests, "grafana data sources"):
        return

    try:
        _, body = http_get(endpoint, "/api/datasources", args.token, args.timeout_seconds)
    except RuntimeError as exc:
        tests.fail("grafana data sources", str(exc))
        return

    if not isinstance(body, list):
        tests.fail("grafana data sources", "unexpected response shape")
        return

    cloudwatch_sources = [item for item in body if item.get("type") == "cloudwatch"]
    if cloudwatch_sources:
        names = ", ".join(item.get("name", "unnamed") for item in cloudwatch_sources)
        tests.pass_("grafana data sources", f"CloudWatch data source found: {names}")
    else:
        tests.fail("grafana data sources", "CloudWatch data source was not found")


def count_collection(body: Any) -> int:
    if isinstance(body, list):
        return len(body)
    if isinstance(body, dict):
        for key in ("items", "results", "alertRules"):
            if isinstance(body.get(key), list):
                return len(body[key])
    return 0


def check_grafana_collection(
    args: argparse.Namespace,
    tests: SmokeTest,
    name: str,
    path: str,
    required: bool,
) -> None:
    endpoint = normalize_endpoint(args.grafana_endpoint)
    if not endpoint:
        message = "GRAFANA_ENDPOINT or WorkspaceEndpoint output missing"
        if required:
            tests.fail(name, message)
        else:
            tests.skip(name, message)
        return
    if not require_token(args, tests, name, required):
        return

    try:
        _, body = http_get(endpoint, path, args.token, args.timeout_seconds)
    except RuntimeError as exc:
        tests.fail(name, str(exc))
        return

    count = count_collection(body)
    if count > 0:
        tests.pass_(name, f"{count} object(s) found")
    elif required:
        tests.fail(name, "no objects found")
    else:
        tests.skip(name, "no objects found")


def main() -> int:
    args = parse_args()
    tests = SmokeTest()

    started_at = time.time()
    load_stack_outputs(args, tests)
    check_workspace(args, tests)
    check_cloudwatch_dashboard(args, tests)
    check_sns_topic(args, tests)
    check_grafana_health(args, tests)
    check_grafana_datasources(args, tests)
    check_grafana_collection(
        args,
        tests,
        "grafana dashboards",
        "/api/search?type=dash-db",
        args.require_grafana_assets,
    )
    check_grafana_collection(
        args,
        tests,
        "grafana contact points",
        "/api/v1/provisioning/contact-points",
        args.require_grafana_assets,
    )
    check_grafana_collection(
        args,
        tests,
        "grafana notification templates",
        "/api/v1/provisioning/templates",
        args.require_grafana_assets,
    )
    check_grafana_collection(
        args,
        tests,
        "grafana alert rules",
        "/api/v1/provisioning/alert-rules",
        args.require_grafana_assets,
    )

    elapsed = time.time() - started_at
    tests.summary()
    print(f"Elapsed: {elapsed:.1f}s")
    return 1 if tests.failed() else 0


if __name__ == "__main__":
    sys.exit(main())
