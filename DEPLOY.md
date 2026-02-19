# Deployment to Google Cloud Run with Supabase

## Prerequisites
- Google Cloud CLI installed (`gcloud`)
- Docker installed
- Supabase project created

## Your Config
- **Supabase Project**: https://pbfeqrtdogwcyyiyeicr.supabase.co
- **Database URL**: Get from Supabase Settings → Database → Connection string (URI)

---

## Step 1: Set up Supabase

1. Go to https://supabase.com and create account (or login)
2. Create new project (or use existing)
3. Go to **SQL Editor** and run the contents of `supabase_setup.sql`
4. Get connection string: **Settings → Database → Connection string**

---

## Step 2: (Optional) Set up Google Cloud Storage

If you want to store PDFs in Google Cloud Storage:

1. Go to https://console.cloud.google.com/storage
2. Create a new bucket (e.g., `school-of-dandori-pdfs`)
3. Go to **Settings → Service Accounts**
4. Create a service account with "Storage Object Admin" role
5. Create a JSON key and copy the contents

---

## Step 3: Deploy

### Option A: Deploy from source (ecloud builds automatically)

```bash
gcloud run deploy school-of-dandori \
  --source . \
  --region us-central1 \
  --set-env-vars DATABASE_URL="postgres://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT].supabase.co:5432/postgres" \
  --allow-unauthenticated
```

### Option B: With Google Cloud Storage

```bash
# Encode your GCS credentials as base64
export GCS_KEY='{"type":"service_account","project_id":"..."...}'
echo $GCS_KEY | base64 -w0

# Deploy with GCS
gcloud run deploy school-of-dandori \
  --source . \
  --region us-central1 \
  --set-env-vars DATABASE_URL="postgres://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT].supabase.co:5432/postgres",GCS_BUCKET_NAME="your-bucket-name",GCS_CREDENTIALS_JSON="$GCS_KEY" \
  --allow-unauthenticated
```

---

## Step 4: Use the API

### Upload a PDF
```bash
curl -X POST https://YOUR-URL/api/upload \
  -F "file=@course.pdf"
```

### Get all courses
```bash
curl https://YOUR-URL/api/courses
```

---

## Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (SQLite)
python api.py

# Run locally with Supabase
export DATABASE_URL="postgres://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT].supabase.co:5432/postgres"
python api.py

# Run locally with GCS
export DATABASE_URL="..." 
export GCS_BUCKET_NAME="your-bucket"
export GCS_CREDENTIALS_JSON='{"type":"service_account"...}'
python api.py
```
