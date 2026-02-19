# Google Cloud Permissions Setup
# Run these commands to fix deployment permissions

# Step 1: Get your project number (run this first)
gcloud projects describe nc-travel-462414 --format="value(projectNumber)"

# Step 2: Grant Cloud Build permissions (replace PROJECT_NUMBER with the number from Step 1)
gcloud projects add-iam-policy-binding nc-travel-462414 \
  --member=serviceAccount:PROJECT_NUMBER@cloudbuild.gserviceaccount.com \
  --role=roles/cloudbuild.builds.builder

gcloud projects add-iam-policy-binding nc-travel-462414 \
  --member=serviceAccount:930810712169-compute@developer.gserviceaccount.com \
  --role=roles/storage.objectViewer

# Step 3: Deploy the app
gcloud run deploy school-of-dandori \
  --source . \
  --region us-central1 \
  --set-env-vars DATABASE_URL="postgres://postgres:s4H1gwGhpB5zgjzM@db.pbfeqrtdogwcyyiyeicr.supabase.co:5432/postgres" \
  --allow-unauthenticated
