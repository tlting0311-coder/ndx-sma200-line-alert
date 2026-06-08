#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-linenotify-498803}"
REGION="${REGION:-asia-east1}"
POOL_ID="${POOL_ID:-github}"
PROVIDER_ID="${PROVIDER_ID:-github}"

if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
  read -r -p "GitHub repository (owner/repo): " GITHUB_REPOSITORY
fi

if [[ ! "$GITHUB_REPOSITORY" =~ ^[^/]+/[^/]+$ ]]; then
  echo "GITHUB_REPOSITORY must look like owner/repo, for example tlting0311/ndx-sma200-line-alert" >&2
  exit 1
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

GITHUB_DEPLOY_SA="github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA="ndx-signal-run@${PROJECT_ID}.iam.gserviceaccount.com"
COMPUTE_BUILD_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
LEGACY_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"

gcloud config set project "$PROJECT_ID"

gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com

gcloud iam service-accounts create github-actions-deploy \
  --display-name="GitHub Actions deploy" || true

for ROLE in \
  roles/cloudbuild.builds.editor \
  roles/run.admin \
  roles/artifactregistry.writer \
  roles/storage.objectAdmin \
  roles/secretmanager.secretAccessor \
  roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${GITHUB_DEPLOY_SA}" \
    --role="$ROLE"
done

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${GITHUB_DEPLOY_SA}" \
  --role="roles/iam.serviceAccountUser"

if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --project="$PROJECT_ID" \
    --location="global" \
    --display-name="GitHub Actions"
fi

ATTRIBUTE_MAPPING="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.actor=assertion.actor"
ATTRIBUTE_CONDITION="assertion.repository=='${GITHUB_REPOSITORY}'"

if gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_ID" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="$ATTRIBUTE_MAPPING" \
    --attribute-condition="$ATTRIBUTE_CONDITION"
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_ID" \
    --display-name="GitHub Actions" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="$ATTRIBUTE_MAPPING" \
    --attribute-condition="$ATTRIBUTE_CONDITION"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${GITHUB_REPOSITORY}" \
  --role="roles/iam.workloadIdentityUser"

# Cloud Build may run as either the Compute Engine default service account or
# the legacy Cloud Build service account, depending on project policy.
for BUILD_SA in "$COMPUTE_BUILD_SA" "$LEGACY_BUILD_SA"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${BUILD_SA}" \
    --role="roles/cloudbuild.builds.builder" || true

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${BUILD_SA}" \
    --role="roles/artifactregistry.writer" || true

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${BUILD_SA}" \
    --role="roles/storage.objectAdmin" || true
done

WORKLOAD_IDENTITY_PROVIDER="$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --format='value(name)')"

cat <<EOF

Configured keyless GitHub Actions authentication.

Next:
1. Open your GitHub repo.
2. Go to Settings -> Secrets and variables -> Actions.
3. Add these repository secrets:
   GCP_PROJECT_ID = ${PROJECT_ID}
   GCP_REGION = ${REGION}
   GCP_WORKLOAD_IDENTITY_PROVIDER = ${WORKLOAD_IDENTITY_PROVIDER}
4. Push to main or run the Deploy to Cloud Run workflow manually.

EOF
