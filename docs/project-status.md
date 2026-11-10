# CS-4075 CloudScale rubric status

This matrix distinguishes implementation evidence from live AWS evidence. Requirements are from `CF-Lec05.1-cloud_project_for23Batch.pdf`; the project is deployed in the user's AWS account in us-east-1. The public demo is https://d39xic7jvhqh80.cloudfront.net.

| Rubric area | Current repository evidence | Status / evidence still needed |
|---|---|---|
| Campus resource board | React UI and FastAPI CRUD, search, uploads, profiles, and notifications | Implemented; local backend suite passed 24 tests and production frontend build passed. Live health endpoint returns HTTP 200. Authenticated CRUD and upload were not exercised against AWS. |
| AI-DLC | `docs/AI-DLC-LOG.md` records this work from the audit forward | Recorded honestly from the available audit onward; earlier sessions were not reconstructed. |
| VPC / subnets / IGW / NAT / security groups | Two public/private AZ pairs, one NAT gateway, CloudFront-only ALB ingress | Deployed in us-east-1. |
| EC2 private ASG (2–4), ALB, CPU scaling | Private ASG, ELB health checks, CPU scaling policy, CloudWatch alarm | Last verified before the user's manual stop: desired capacity 2 and both targets healthy. The user reports stopping one instance and not seeing a replacement; current group health needs recheck. |
| S3 uploads, versioning, lifecycle, CloudFront | Private bucket, OAC frontend origin, versioning/lifecycle, S3 adapter | Deployed. Cognito-configured frontend assets were uploaded and CloudFront invalidation completed. Live file upload was not exercised. |
| Primary data store | DynamoDB table with four GSIs and private gateway endpoint | Deployed; live CRUD/data persistence was not exercised. |
| Async Lambda | SQS-triggered image processor, DLQ, scoped IAM, partial batch responses | Function and event mapping are deployed; function is Active. A real queued image invocation was not verified. |
| SQS / SNS | Queue/DLQ and encrypted SNS topic | Deployed. Email subscription confirmation and message delivery were not verified. |
| Cognito sign-up/sign-in | User pool/client, browser sign-up/confirmation and token verification | Pool/client deployed; browser is configured for Cognito. End-to-end signup and confirmation remain unverified. |
| IAM least privilege | Separate EC2, Lambda, and SageMaker roles with scoped policies | Roles and runtime policies deployed. Temporary deployer policy is broad and should be removed or reduced by an account administrator after grading. |
| Route 53 / CloudWatch / budget | Optional hosted-zone alias, dashboard, alarms, 80/100% monthly budget alerts | Dashboard, alarms, and $30 monthly alert deployed. Route 53 custom domain is not configured. The alert is not a spending cap. |
| SageMaker | Optional Serverless endpoint resource and app integration | Disabled to conserve the reported $100 credits; no trained model artifact or endpoint is included. Category suggestions use the local provider. |
| Bedrock | Real `Converse` integration and user-facing description assist exist | API reports Bedrock selected with no configuration warnings; a real model invocation was not verified. |
| GitHub private repo/history/collaborator | Component-wise local history uses Nov 10 only under the user's reported course-staff accommodation | Private repository publication and evaluator collaborator invitations are pending. |
| Architecture/report/demo/cleanup evidence | Architecture, deployment, cost docs, this report, and `docs/video-demo-guide.md` | User reports the video is recorded; the video file is not in this checkout. Live component/billing screenshots and post-grading teardown evidence remain. The stack is live and billable. |

## Local verification

- `backend/.venv/bin/python -m pytest`: **24 passed** after adding the missing test helper import.
- `cd frontend && npm run build`: **passed**.
- `terraform fmt -check -recursive`: **passed**.
- `terraform validate`: **passed with deprecation warnings** after initializing AWS/archive/random providers.
- Enabled AWS Terraform plan: **62 creates, 0 updates, 0 deletes**. Apply partially succeeded, then stopped because the current user's policy lacks `iam:ListAttachedRolePolicies`. Terraform state tracks the live partial stack.
- Backend tests, frontend build, and Terraform formatting/validation: **passed** as recorded above.
- AWS site and API health: **verified** (`/` and `/api/health` return HTTP 200; API reports Cognito, DynamoDB, S3, Bedrock, local categories, and AWS notifications).
- ALB target health was **2 of 2 healthy** before the user's later manual stop. Auto Scaling desired capacity was **2**; refresh was cancelled at 50% due stale ELB health data. Current replacement status is unverified.
- CloudFront invalidation completed after publishing the Cognito-enabled frontend.
- Authenticated browser E2E, CRUD/upload, real Lambda invocation, SNS delivery, Bedrock inference, load/scaling demonstration, and SageMaker endpoint: **not verified or not deployed**.

## Approval boundary

The checked-in Terraform defaults to no AWS resources; the ignored local `terraform.tfvars` enables this deployment. The user reports $100 in credits. NAT Gateway, ALB, two EC2 instances, and CloudFront are live and incur charges. Cost Explorer is unavailable. The $30 budget is an alert, not a cap. Keep SageMaker disabled. Ask an AWS account administrator to remove the temporary broad deployment policy after grading. The AWS account owner/admin controls IAM policy changes; root login is not required if an IAM administrator is available. No credentials should be shared.
