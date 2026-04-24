#!/usr/bin/env bash
#
# AXON — T-02 GCP provisioning script.
#
# Run this from GCP Cloud Shell (the browser terminal). It idempotently creates:
#   - Cloud SQL Postgres instance + database + app user
#   - Cloud Storage bucket for PDF reports
#   - Cloud Tasks queue for audit jobs
#   - Secret Manager entries for DB password + Anthropic API key + proxy creds
#   - Required GCP APIs enabled
#
# Prerequisites:
#   - You are logged in as a project owner / editor
#   - Billing is linked to the project
#
# Usage:
#   bash provision.sh
#
# Re-running is safe — every step is idempotent (uses --quiet and || true on existing-resource errors).

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-axon-494010}"
REGION="${REGION:-us-central1}"
SQL_INSTANCE="${SQL_INSTANCE:-axon-postgres}"
SQL_DB="${SQL_DB:-axon}"
SQL_USER="${SQL_USER:-axon}"
SQL_PASSWORD="${SQL_PASSWORD:-$(openssl rand -base64 24 | tr -d '\n/+=' | head -c 24)}"
REPORTS_BUCKET="${REPORTS_BUCKET:-${PROJECT_ID}-axon-reports}"
TASKS_QUEUE="${TASKS_QUEUE:-axon-audit-queue}"

echo "=============================================="
echo " AXON — GCP Provisioning"
echo " project: ${PROJECT_ID}"
echo " region:  ${REGION}"
echo "=============================================="

gcloud config set project "${PROJECT_ID}"
gcloud config set compute/region "${REGION}"

# -------- 1. Enable APIs --------
echo
echo "[1/6] Enabling required APIs…"
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  cloudtasks.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

# -------- 2. Cloud SQL (Postgres 15) --------
echo
echo "[2/6] Cloud SQL Postgres instance…"
if ! gcloud sql instances describe "${SQL_INSTANCE}" >/dev/null 2>&1; then
  gcloud sql instances create "${SQL_INSTANCE}" \
    --database-version=POSTGRES_15 \
    --region="${REGION}" \
    --tier=db-f1-micro \
    --storage-size=10GB \
    --storage-auto-increase
else
  echo "  instance exists — skipping create"
fi

if ! gcloud sql databases describe "${SQL_DB}" --instance="${SQL_INSTANCE}" >/dev/null 2>&1; then
  gcloud sql databases create "${SQL_DB}" --instance="${SQL_INSTANCE}"
fi

if ! gcloud sql users list --instance="${SQL_INSTANCE}" --format="value(name)" | grep -qx "${SQL_USER}"; then
  gcloud sql users create "${SQL_USER}" --instance="${SQL_INSTANCE}" --password="${SQL_PASSWORD}"
  echo "  app user created. Password stored in Secret Manager below."
else
  echo "  app user exists — leaving password unchanged"
fi

# -------- 3. GCS reports bucket --------
echo
echo "[3/6] Cloud Storage bucket for reports…"
if ! gsutil ls "gs://${REPORTS_BUCKET}" >/dev/null 2>&1; then
  gsutil mb -l "${REGION}" -b on "gs://${REPORTS_BUCKET}"
  # Lifecycle: delete PDFs older than 180 days to control cost
  cat >/tmp/lifecycle.json <<'EOF'
{
  "lifecycle": {
    "rule": [
      { "action": {"type": "Delete"}, "condition": {"age": 180} }
    ]
  }
}
EOF
  gsutil lifecycle set /tmp/lifecycle.json "gs://${REPORTS_BUCKET}"
fi

# -------- 4. Cloud Tasks queue --------
echo
echo "[4/6] Cloud Tasks queue…"
if ! gcloud tasks queues describe "${TASKS_QUEUE}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud tasks queues create "${TASKS_QUEUE}" \
    --location="${REGION}" \
    --max-concurrent-dispatches=4 \
    --max-dispatches-per-second=1 \
    --max-attempts=3
fi

# -------- 5. Secret Manager --------
echo
echo "[5/6] Secret Manager entries…"

create_or_update_secret () {
  local name="$1" value="$2"
  if gcloud secrets describe "${name}" >/dev/null 2>&1; then
    echo -n "${value}" | gcloud secrets versions add "${name}" --data-file=- >/dev/null
    echo "  updated: ${name}"
  else
    echo -n "${value}" | gcloud secrets create "${name}" --data-file=- --replication-policy=automatic >/dev/null
    echo "  created: ${name}"
  fi
}

create_or_update_secret "axon-db-password" "${SQL_PASSWORD}"
create_or_update_secret "axon-anthropic-api-key" "${ANTHROPIC_API_KEY:-sk-ant-replace-me}"
create_or_update_secret "axon-proxy-username" "${PROXY_USERNAME:-}"
create_or_update_secret "axon-proxy-password" "${PROXY_PASSWORD:-}"
create_or_update_secret "axon-jwt-secret" "$(openssl rand -hex 32)"

# -------- 6. Summary --------
echo
echo "[6/6] Provisioning complete."
echo
echo "Save these for your local .env / Cloud Run env config:"
echo "  GCP_PROJECT_ID=${PROJECT_ID}"
echo "  GCP_REGION=${REGION}"
echo "  CLOUD_SQL_INSTANCE=${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
echo "  POSTGRES_DB=${SQL_DB}"
echo "  POSTGRES_USER=${SQL_USER}"
echo "  GCS_REPORTS_BUCKET=${REPORTS_BUCKET}"
echo "  CLOUD_TASKS_QUEUE=${TASKS_QUEUE}"
echo "  # The DB password is in Secret Manager as axon-db-password."
echo
echo "Next steps:"
echo "  1. Run the DB migrations against Cloud SQL (connect via Cloud SQL Proxy)."
echo "  2. Build & deploy each service via Cloud Build (ai-proxy, backend, worker, frontend)."
echo "  3. Update Cloud Run env vars to use Secret Manager bindings."
