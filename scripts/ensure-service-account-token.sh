#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ID="${WORKSPACE_ID:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-github-actions-deployer}"
GRAFANA_ROLE="${GRAFANA_ROLE:-ADMIN}"
TOKEN_NAME="${TOKEN_NAME:-github-actions-token}"
TOKEN_TTL_SECONDS="${TOKEN_TTL_SECONDS:-3600}"

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/ensure-service-account-token.sh --workspace-id <id> [options]

Options:
  --workspace-id <id>              AWS Managed Grafana workspace ID.
  --region <region>                AWS region. Defaults to AWS_REGION or us-east-1.
  --service-account-name <name>    Service account name. Defaults to github-actions-deployer.
  --grafana-role <role>            ADMIN, EDITOR, or VIEWER. Defaults to ADMIN.
  --token-name <name>              Token name prefix. Defaults to github-actions-token.
  --token-ttl-seconds <seconds>    Token TTL. Defaults to 3600.

The token key is printed to stdout. Logs are printed to stderr.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace-id)
      WORKSPACE_ID="$2"
      shift 2
      ;;
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --service-account-name)
      SERVICE_ACCOUNT_NAME="$2"
      shift 2
      ;;
    --grafana-role)
      GRAFANA_ROLE="$2"
      shift 2
      ;;
    --token-name)
      TOKEN_NAME="$2"
      shift 2
      ;;
    --token-ttl-seconds)
      TOKEN_TTL_SECONDS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$WORKSPACE_ID" ]]; then
  echo "WORKSPACE_ID or --workspace-id is required" >&2
  usage
  exit 2
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

SERVICE_ACCOUNT_ID="$(
  aws grafana list-workspace-service-accounts \
    --workspace-id "$WORKSPACE_ID" \
    --region "$AWS_REGION" \
    --query "serviceAccounts[?name=='${SERVICE_ACCOUNT_NAME}'] | [0].id" \
    --output text
)"

if [[ -z "$SERVICE_ACCOUNT_ID" || "$SERVICE_ACCOUNT_ID" == "None" ]]; then
  echo "Creating Grafana service account $SERVICE_ACCOUNT_NAME" >&2
  SERVICE_ACCOUNT_ID="$(
    aws grafana create-workspace-service-account \
      --workspace-id "$WORKSPACE_ID" \
      --name "$SERVICE_ACCOUNT_NAME" \
      --grafana-role "$GRAFANA_ROLE" \
      --region "$AWS_REGION" \
      --query "id" \
      --output text
  )"
else
  echo "Using existing Grafana service account $SERVICE_ACCOUNT_NAME" >&2
fi

TOKEN_JSON="$(
  aws grafana create-workspace-service-account-token \
    --workspace-id "$WORKSPACE_ID" \
    --service-account-id "$SERVICE_ACCOUNT_ID" \
    --name "${TOKEN_NAME}-$(date +%s)" \
    --seconds-to-live "$TOKEN_TTL_SECONDS" \
    --region "$AWS_REGION" \
    --output json
)"

python3 -c 'import json,sys; print(json.load(sys.stdin)["serviceAccountToken"]["key"])' <<< "$TOKEN_JSON"
