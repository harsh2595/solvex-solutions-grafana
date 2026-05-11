"""CloudFormation custom resource for Amazon Managed Grafana plugin installation."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import boto3


LOG = logging.getLogger()
LOG.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def send_response(
    event: dict[str, Any],
    context: Any,
    status: str,
    data: dict[str, Any],
    reason: str | None = None,
    physical_id: str | None = None,
) -> None:
    body = {
        "Status": status,
        "Reason": reason or f"See CloudWatch Logs: {context.log_stream_name}",
        "PhysicalResourceId": physical_id
        or event.get("PhysicalResourceId")
        or context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "NoEcho": False,
        "Data": data,
    }
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        event["ResponseURL"],
        data=payload,
        method="PUT",
        headers={"content-type": "", "content-length": str(len(payload))},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        LOG.info("CloudFormation response status: %s", response.status)


def parse_plugins(value: Any) -> list[dict[str, str]]:
    raw_plugins = value if isinstance(value, list) else str(value or "").split(",")
    plugins = []
    for raw_item in raw_plugins:
        item = str(raw_item).strip()
        if not item:
            continue
        if "@" in item:
            plugin_id, version = item.split("@", 1)
            plugins.append({"id": plugin_id.strip(), "version": version.strip()})
        else:
            plugins.append({"id": item})
    return plugins


def wait_for_workspace(client: Any, workspace_id: str) -> dict[str, Any]:
    for _ in range(60):
        workspace = client.describe_workspace(workspaceId=workspace_id)["workspace"]
        status = workspace["status"]
        LOG.info("Workspace %s status: %s", workspace_id, status)
        if status == "ACTIVE":
            return workspace
        if status.endswith("FAILED") or status == "DELETING":
            raise RuntimeError(f"Workspace {workspace_id} is {status}")
        time.sleep(10)
    raise TimeoutError(f"Workspace {workspace_id} did not become ACTIVE within 10 minutes")


def find_or_create_service_account(client: Any, workspace_id: str, name: str) -> str:
    next_token = None
    while True:
        kwargs: dict[str, Any] = {"workspaceId": workspace_id, "maxResults": 100}
        if next_token:
            kwargs["nextToken"] = next_token
        response = client.list_workspace_service_accounts(**kwargs)
        for account in response.get("serviceAccounts", []):
            disabled = str(account.get("isDisabled", "false")).lower() == "true"
            if account.get("name") == name and not disabled:
                return account["id"]
        next_token = response.get("nextToken")
        if not next_token:
            break

    response = client.create_workspace_service_account(
        workspaceId=workspace_id,
        name=name,
        grafanaRole="ADMIN",
    )
    return response["id"]


def create_token(
    client: Any,
    workspace_id: str,
    service_account_id: str,
    ttl_seconds: int,
    request_id: str,
) -> str:
    response = client.create_workspace_service_account_token(
        workspaceId=workspace_id,
        serviceAccountId=service_account_id,
        name=f"cfn-plugin-install-{request_id[:8]}",
        secondsToLive=int(ttl_seconds),
    )
    return response["serviceAccountToken"]["key"]


def grafana_post(endpoint: str, token: str, path: str, payload: dict[str, Any]) -> int:
    endpoint = endpoint.rstrip("/")
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint}{path}",
        data=body,
        method="POST",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        if exc.code in (200, 202, 409):
            return exc.code
        raise RuntimeError(f"Grafana API {path} failed with HTTP {exc.code}: {text}") from exc


def handler(event: dict[str, Any], context: Any) -> None:
    LOG.info("Event: %s", json.dumps({k: v for k, v in event.items() if k != "ResponseURL"}))
    props = event.get("ResourceProperties", {})
    workspace_id = props["WorkspaceId"]
    physical_id = f"grafana-plugins-{workspace_id}"

    try:
        if event["RequestType"] == "Delete":
            send_response(
                event,
                context,
                "SUCCESS",
                {"Message": "Delete does not uninstall plugins."},
                physical_id=physical_id,
            )
            return

        plugins = parse_plugins(props.get("PluginIds", ""))
        if not plugins:
            send_response(event, context, "SUCCESS", {"InstalledPlugins": []}, physical_id=physical_id)
            return

        client = boto3.client("grafana")
        workspace = wait_for_workspace(client, workspace_id)
        endpoint = props.get("WorkspaceEndpoint") or workspace["endpoint"]
        service_account_id = find_or_create_service_account(
            client,
            workspace_id,
            props.get("ServiceAccountName", "cfn-plugin-installer"),
        )
        token = create_token(
            client,
            workspace_id,
            service_account_id,
            int(props.get("TokenTtlSeconds", 3600)),
            event["RequestId"],
        )

        installed = []
        for plugin in plugins:
            plugin_id = plugin["id"]
            payload = {}
            if plugin.get("version"):
                payload["version"] = plugin["version"]
            safe_id = urllib.parse.quote(plugin_id, safe="")
            status = grafana_post(endpoint, token, f"/api/plugins/{safe_id}/install", payload)
            installed.append(
                {
                    "id": plugin_id,
                    "version": plugin.get("version", "latest-compatible"),
                    "status": status,
                }
            )

        send_response(
            event,
            context,
            "SUCCESS",
            {"InstalledPlugins": installed},
            physical_id=physical_id,
        )
    except Exception as exc:
        LOG.exception("Plugin installation failed")
        send_response(
            event,
            context,
            "FAILED",
            {"Error": str(exc)},
            reason=str(exc),
            physical_id=physical_id,
        )
