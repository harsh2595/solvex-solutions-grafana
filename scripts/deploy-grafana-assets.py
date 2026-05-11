#!/usr/bin/env python3
"""Deploy Grafana folders, data sources, dashboards, and alerting assets."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROVENANCE_HEADERS = {"X-Disable-Provenance": "true"}


class GrafanaClient:
    def __init__(self, endpoint: str, token: str, timeout: int = 30) -> None:
        self.endpoint = normalize_endpoint(endpoint)
        self.token = token
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        ok: tuple[int, ...] = (200,),
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = urllib.parse.urljoin(f"{self.endpoint}/", path.lstrip("/"))
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if headers:
            request_headers.update(headers)

        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers=request_headers,
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8")
                if response.status not in ok:
                    raise RuntimeError(f"{method} {path} returned HTTP {response.status}: {response_body}")
                return parse_response(response_body)
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in ok:
                return parse_response(response_body)
            raise RuntimeError(f"{method} {path} returned HTTP {exc.code}: {response_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc

    def get_optional(self, path: str) -> Any | None:
        try:
            return self.request("GET", path)
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy Grafana assets.")
    parser.add_argument(
        "--endpoint",
        default=os.getenv("GRAFANA_ENDPOINT"),
        required=not os.getenv("GRAFANA_ENDPOINT"),
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GRAFANA_TOKEN"),
        required=not os.getenv("GRAFANA_TOKEN"),
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--sns-topic-arn", default=os.getenv("SNS_TOPIC_ARN", ""))
    parser.add_argument("--environment", default=os.getenv("ENVIRONMENT", "dev"))
    parser.add_argument("--grafana-dir", default="grafana")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--skip-alerting", action="store_true")
    return parser.parse_args()


def normalize_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip().rstrip("/")
    if endpoint.startswith("https://") or endpoint.startswith("http://"):
        return endpoint
    return f"https://{endpoint}"


def parse_response(response_body: str) -> Any:
    if not response_body:
        return None
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return response_body


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def render_value(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        rendered = value
        for key, replacement in variables.items():
            rendered = rendered.replace(f"${{{key}}}", replacement)
        return rendered
    if isinstance(value, list):
        return [render_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: render_value(item, variables) for key, item in value.items()}
    return value


def upsert_folder(client: GrafanaClient, folder: dict[str, Any]) -> None:
    uid = folder["uid"]
    title = folder["title"]
    existing = client.get_optional(f"/api/folders/{urllib.parse.quote(uid, safe='')}")
    if existing:
        client.request(
            "PUT",
            f"/api/folders/{urllib.parse.quote(uid, safe='')}",
            {"title": title, "overwrite": True},
        )
        print(f"Updated folder {uid}")
        return

    client.request("POST", "/api/folders", {"uid": uid, "title": title}, ok=(200, 201))
    print(f"Created folder {uid}")


def upsert_datasource(client: GrafanaClient, datasource: dict[str, Any]) -> None:
    uid = datasource["uid"]
    escaped_uid = urllib.parse.quote(uid, safe="")
    existing = client.get_optional(f"/api/datasources/uid/{escaped_uid}")
    if existing:
        body = {
            "id": existing.get("id"),
            "orgId": existing.get("orgId"),
            **datasource,
        }
        client.request("PUT", f"/api/datasources/uid/{escaped_uid}", body)
        print(f"Updated data source {uid}")
        return

    client.request("POST", "/api/datasources", datasource, ok=(200, 201))
    print(f"Created data source {uid}")


def upsert_templates(client: GrafanaClient, templates: list[dict[str, Any]]) -> None:
    for template in templates:
        name = template["name"]
        body = {"template": template["template"]}
        if template.get("version"):
            body["version"] = template["version"]
        client.request(
            "PUT",
            f"/api/v1/provisioning/templates/{urllib.parse.quote(name, safe='')}",
            body,
            ok=(200, 202),
            headers=PROVENANCE_HEADERS,
        )
        print(f"Upserted notification template {name}")


def upsert_contact_points(client: GrafanaClient, contact_points: list[dict[str, Any]]) -> None:
    existing_points = client.request("GET", "/api/v1/provisioning/contact-points")
    existing_uids = {
        item.get("uid")
        for item in existing_points
        if isinstance(item, dict) and item.get("uid")
    }
    for contact_point in contact_points:
        uid = contact_point.get("uid")
        if uid and uid in existing_uids:
            client.request(
                "PUT",
                f"/api/v1/provisioning/contact-points/{urllib.parse.quote(uid, safe='')}",
                contact_point,
                ok=(200, 202),
                headers=PROVENANCE_HEADERS,
            )
            print(f"Updated contact point {uid}")
        else:
            client.request(
                "POST",
                "/api/v1/provisioning/contact-points",
                contact_point,
                ok=(200, 201, 202),
                headers=PROVENANCE_HEADERS,
            )
            print(f"Created contact point {uid or contact_point.get('name')}")


def replace_notification_policy(client: GrafanaClient, policy: dict[str, Any]) -> None:
    client.request(
        "PUT",
        "/api/v1/provisioning/policies",
        policy,
        ok=(200, 202),
        headers=PROVENANCE_HEADERS,
    )
    print("Replaced notification policy tree")


def upsert_rule_groups(client: GrafanaClient, rule_groups: list[dict[str, Any]]) -> None:
    for group in rule_groups:
        folder_uid = group["folderUid"]
        name = group["name"]
        body = {
            "folderUid": folder_uid,
            "interval": group.get("interval", 60),
            "title": name,
            "rules": group["rules"],
        }
        client.request(
            "PUT",
            "/api/v1/provisioning/folder/"
            f"{urllib.parse.quote(folder_uid, safe='')}/rule-groups/"
            f"{urllib.parse.quote(name, safe='')}",
            body,
            ok=(200, 202),
            headers=PROVENANCE_HEADERS,
        )
        print(f"Upserted alert rule group {name}")


def main() -> int:
    args = parse_args()
    grafana_dir = Path(args.grafana_dir)
    variables = {
        "AWS_REGION": args.region,
        "SNS_TOPIC_ARN": args.sns_topic_arn,
        "ENVIRONMENT": args.environment,
        "GRAFANA_ENDPOINT": normalize_endpoint(args.endpoint),
    }
    client = GrafanaClient(args.endpoint, args.token, timeout=args.timeout_seconds)

    folders = render_value(load_json(grafana_dir / "provisioning" / "folders.json"), variables)
    for folder in folders:
        upsert_folder(client, folder)

    datasources = render_value(load_json(grafana_dir / "provisioning" / "datasources.json"), variables)
    for datasource in datasources:
        upsert_datasource(client, datasource)

    for dashboard_path in sorted((grafana_dir / "dashboards").glob("*.json")):
        rendered = render_value(load_json(dashboard_path), variables)
        folder_uid = rendered.get("folderUid")
        dashboard = rendered["dashboard"] if "dashboard" in rendered else rendered
        dashboard["id"] = None
        payload = {
            "dashboard": dashboard,
            "folderUid": folder_uid,
            "overwrite": True,
            "message": f"Deployed {dashboard_path.name} from repository automation",
        }
        if not folder_uid:
            payload.pop("folderUid")
        response = client.request("POST", "/api/dashboards/db", payload, ok=(200, 201))
        status = response.get("status", "ok") if isinstance(response, dict) else "ok"
        print(f"Upserted dashboard {dashboard.get('uid', dashboard_path.stem)} ({status})")

    if args.skip_alerting:
        print("Skipping alerting assets")
        return 0

    alerts_dir = grafana_dir / "alerts"
    templates = render_value(load_json(alerts_dir / "notification-templates.json"), variables)
    upsert_templates(client, templates)

    contact_points = render_value(load_json(alerts_dir / "contact-points.json"), variables)
    upsert_contact_points(client, contact_points)

    policy = render_value(load_json(alerts_dir / "notification-policies.json"), variables)
    replace_notification_policy(client, policy)

    rule_groups = render_value(load_json(alerts_dir / "rule-groups.json"), variables)
    upsert_rule_groups(client, rule_groups)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
