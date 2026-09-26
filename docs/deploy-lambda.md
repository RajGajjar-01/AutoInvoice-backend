# Beta deploy: AWS Lambda + Supabase + Upstash

Backend runs as a Lambda container image (`Dockerfile.lambda`, handler
`app.lambda_handler.handler` via Mangum) behind a **Function URL**. Frontend is on
Cloudflare (see the frontend repo's `deploy/cloudflare` branch).

## 1. Env vars (set on the Lambda function)

All other variables are the same as in `deploy.md`.

```
ENVIRONMENT=production
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
DB_SSLMODE=require
DB_POOL=null          # no pooling inside Lambda; Supabase's pooler does it
DB_PREPARE=false      # required for the transaction pooler (port 6543)
REDIS_URL=rediss://default:<token>@<host>.upstash.io:6379
FRONTEND_HOST=https://<your-site>.workers.dev
BACKEND_CORS_ORIGINS=https://<your-site>.workers.dev
GOOGLE_REDIRECT_URI=https://<function-url>/api/v1/google/callback
```

Leave `OPENWA_*` unset (WhatsApp is disabled for beta).

To switch databases, only change the env vars:
- **RDS:** point `DATABASE_URL` at RDS, keep `DB_SSLMODE=require`, set `DB_PREPARE=true`.
- **Local Postgres:** unset all `DB_*` vars.

## 2. Migrations (manual — never on cold start)

Run from your machine or CI before deploying new code. Use the **session pooler
(port 5432)** or the direct connection for DDL:

```
DATABASE_URL='postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
DB_SSLMODE=require uv run alembic upgrade head
DATABASE_URL=... DB_SSLMODE=require uv run python -m app.initial_data   # first deploy only
```

## 3. Build & push image

Console-only: use a CodeBuild project with `buildspec.lambda.yml` (see that file). With the CLI:

```
aws ecr create-repository --repository-name autoinvoice-backend   # once
aws ecr get-login-password | docker login --username AWS --password-stdin <acct>.dkr.ecr.<region>.amazonaws.com
docker build --provenance=false -f Dockerfile.lambda -t <acct>.dkr.ecr.<region>.amazonaws.com/autoinvoice-backend:latest .
docker push <acct>.dkr.ecr.<region>.amazonaws.com/autoinvoice-backend:latest
```

Create the function from that image with an **x86_64** architecture (or build with
`--platform linux/arm64` and choose arm64). Set memory to 1024 MB and the timeout to 30 s.
Then enable a **Function URL** with auth type `NONE`. Don't configure CORS on the
Function URL, because FastAPI already sends the CORS headers.

## 4. Keep Supabase awake

A free Supabase project pauses after 7 days without any database queries. Add an
EventBridge Scheduler rule that invokes the function once a day with an HTTP event
for `GET /health`. That query is enough to keep it awake.

## Local smoke test (Lambda Runtime Interface Emulator)

```
docker build -f Dockerfile.lambda -t autoinvoice-lambda .
docker run --rm --network host --env-file .env -e DB_POOL=null \
  -v /path/to/aws-lambda-rie:/rie:ro --entrypoint /rie autoinvoice-lambda \
  python -m awslambdaric app.lambda_handler.handler
curl -XPOST localhost:8080/2015-03-31/functions/function/invocations \
  -d '{"version":"2.0","rawPath":"/health","rawQueryString":"","headers":{},"requestContext":{"http":{"method":"GET","path":"/health","sourceIp":"1.2.3.4"}},"isBase64Encoded":false}'
```
