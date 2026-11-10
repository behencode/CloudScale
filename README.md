# CampusConnect

CampusConnect is a university community board for lost and found items, textbook exchange, housing, events, and community requests. The repository contains a FastAPI backend, a React/Vite frontend, local SQLite and filesystem adapters, optional AWS adapters, and a Lambda image worker.

## Local development

Requirements: Python 3.11 or later and Node.js 20 or later.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The Vite server proxies `/api` and `/uploads` to the backend on port 8000. The API documentation is at http://127.0.0.1:8000/docs. By default the app uses SQLite, local file uploads, local password authentication, template description assistance, keyword category suggestions, and in-app notifications. It does not call AWS in this configuration.

To configure local settings, copy `.env.example` to `backend/.env`. Set a private `JWT_SECRET` before using the app beyond local experimentation. Runtime SQLite data and uploads are written beneath `backend/data` when starting the backend from that directory; choose absolute `SQLITE_PATH` and `UPLOAD_DIR` values when you need stable locations independent of the launch directory.

## Project map

- `backend/app/`: API, authentication, schemas, persistence, storage, AI, and notification adapters.
- `backend/lambda/image_processor/`: SQS-triggered image processor source. Pillow must be packaged with the Lambda deployment.
- `backend/tests/`: API, adapter, and Lambda unit tests.
- `frontend/src/`: React application and pages.
- `docs/`: architecture, deployment, cost, and development evidence.

## AWS and deployment status

The deployed demo is available at [https://d39xic7jvhqh80.cloudfront.net](https://d39xic7jvhqh80.cloudfront.net). It uses Cognito authentication, DynamoDB, S3, Bedrock descriptions, local category suggestions, and AWS notifications. `/api/health` returned HTTP 200 at the last check. Both load balancer targets were healthy before the user manually stopped one EC2 instance; replacement status has not been rechecked. End-to-end signup, listing CRUD, uploads, queued image processing, SNS delivery, and Bedrock inference have not yet been verified.

The Terraform root is in `infrastructure/terraform`. Resources are disabled by default. The live stack uses an ignored local `terraform.tfvars`, which is not included in the repository. The deployed $30 budget is an alert, not a cap; NAT Gateway, ALB, EC2, and CloudFront continue to incur charges while left online. SageMaker is disabled to conserve credits. See the deployment guide for current status and cleanup steps.

## Local video demo with sample data

The video demo uses a separate local SQLite database and fictional listings. It does not change the AWS deployment.

```bash
cd /Users/m1pro/CloudScale
backend/.venv/bin/python scripts/seed_demo.py
cd backend
APP_MODE=local AUTH_MODE=local DATABASE_BACKEND=sqlite STORAGE_BACKEND=local \
DESCRIPTION_PROVIDER=local CATEGORY_PROVIDER=local NOTIFICATION_BACKEND=local \
JWT_SECRET=local-video-demo-only-change-me-32bytes \
SQLITE_PATH="$PWD/data/campusconnect-demo.db" \
UPLOAD_DIR="$PWD/data/demo-uploads" \
.venv/bin/uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd /Users/m1pro/CloudScale/frontend
npm run dev
```

Open http://localhost:5173 and sign in with `demo@example.com` / `CampusDemo123!`. This is a fictional local-only account. The sample database is ignored by Git.

For a step-by-step recording outline, see [the video demo guide](docs/video-demo-guide.md).

## Validation status

Backend tests passed (24 tests), the frontend production build passed, and Terraform formatting/validation passed with AWS-provider deprecation warnings. The live frontend and API health endpoint return HTTP 200. Both EC2 instances and ALB targets are healthy. Authenticated browser E2E, live CRUD/uploads, Lambda invocation, SNS delivery, Bedrock inference, and load/scaling demonstration remain unverified.
