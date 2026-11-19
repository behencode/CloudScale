# AI-DLC activity log

This log starts with the available repository audit. It does not claim earlier AI-DLC sessions or implementation decisions that were not recorded.

## 2026-11-10 — Audit findings and remediation

- Reviewed `docs/Audit` against the current source tree.
- Confirmed the audit's Cognito keyword mismatch, missing bearer OpenAPI scheme, photo edit/removal flow, intent-list drift, upload cleanup, root runtime-data ignore, and non-JSON API response findings are addressed in the current working tree.
- Added project, architecture, deployment, and cost documentation based on implemented source and explicitly marked cloud deployment as absent.
- Validation commands have not been run in this work session. No Terraform configuration or deployed infrastructure is claimed.

## Follow-up evidence

Append dated entries after running dependency installation, backend tests, frontend build, browser smoke flows, or infrastructure validation. Record the exact command and its actual result; do not infer success from source inspection.

## 2026-11-10 — CS-4075 implementation and local verification

- Read the supplied CS-4075 CloudScale project specification and derived the rubric status matrix in `docs/project-status.md`.
- Added AWS Terraform resources for a two-AZ VPC, NAT, private EC2 ASG, ALB, S3/CloudFront, DynamoDB, Cognito, SQS/DLQ/Lambda, SNS, IAM roles, CloudWatch, budget alerts, and an optional SageMaker endpoint. The master switch defaults to `false`; no AWS resources were created.
- Added frontend build, Lambda packaging, and load-test scripts plus account-specific deployment instructions.
- `terraform -chdir=infrastructure/terraform fmt -check -recursive`: passed.
- `terraform -chdir=infrastructure/terraform validate`: passed with provider deprecation warnings.
- `terraform -chdir=infrastructure/terraform plan -input=false` with the default master switch off: no changes.
- `backend/.venv/bin/python -m pytest`: 24 passed.
- `cd frontend && npm run build`: passed.
- AWS apply, model training/endpoint, browser E2E, scaling/load evidence, report PDF, demo video, external GitHub setup, and teardown remain outstanding.

## 2026-11-10 — AWS deployment preflight

- Confirmed the configured AWS identity and target region (`us-east-1` for this project). Cost Explorer and CloudFormation stack listing are not available to this identity; no CampusConnect VPC or bucket was found in the target region.
- Generated a 63-resource plan with a $30 monthly budget alert, NAT enabled, and SageMaker disabled. The plan contained no updates or deletes.
- Apply was attempted under explicit user authorization but AWS denied resource creation, including `ec2:CreateVpc`, `iam:CreateRole`, `s3:CreateBucket`, `dynamodb:CreateTable`, SQS, SNS, Cognito, CloudFront, Budgets, and CloudWatch actions. Terraform state contains no AWS resources; only local data and a random value are recorded.
- Replaced the denied SSM AMI lookup with an EC2 image query and used the verified us-east-1 CloudFront prefix-list ID, preserving restricted ALB ingress. Added `infrastructure/terraform/deployer-policy.json` for a dedicated temporary deployment identity.
- A $100 credit balance was reported by the user. The $30 budget is an alert threshold, not a spending cap. Deploy and verify only with the newly authorized identity; review current spend because Cost Explorer access is unavailable.
- No report PDF has been generated, per the user's instruction to deploy and finalize first.

## 2026-11-10 — Deployment continuation

- The user updated the current IAM identity and the refreshed 62-resource plan succeeded with 0 changes and 0 deletes.
- The apply created the budget, CloudFront distribution/OAC, VPC, public and private subnets, Internet Gateway, NAT Gateway, route tables, S3/DynamoDB endpoints, security groups, ALB/listener/rule, S3 bucket/security/versioning/lifecycle/assets, DynamoDB table, Cognito pool/client, SQS queues, SNS topic/subscription, Lambda log group, and two IAM roles.
- The apply stopped while refreshing IAM roles because the updated policy omits `iam:ListAttachedRolePolicies`. Terraform state records those resources. NAT Gateway, ALB, and CloudFront are active and billable.
- Lambda zip is built at `infrastructure/terraform/.build/image_processor.zip`. Frontend assets currently deployed were built without Cognito settings and must be rebuilt and uploaded after completing the stack.
- The user requests fastest possible submission; report PDF remains deferred until deployment and finalization.

## 2026-11-10 — Deployment completion and evidence

- The deployment used the `cloudscale-developer` IAM identity; no root credentials were requested or shared. The account's IAM administrator controls changes to IAM policies.
- Completed the AWS deployment with the current authorized identity. The backend is publicly reachable through CloudFront; `GET /api/health` returned HTTP 200 and reported AWS mode, Cognito, DynamoDB, S3, Bedrock descriptions, local categories, AWS notifications, and no warnings.
- Rebuilt the frontend with Cognito region `us-east-1` and the deployed public app client ID, uploaded it to the existing private S3 origin, and completed CloudFront invalidation `I477NMYV461VHHIHNWIVXLMFPN`.
- Verified two EC2 instances InService/Healthy and both ALB targets healthy. Cancelled an Auto Scaling refresh that remained at 50% with stale health-data reasons despite both targets becoming healthy. Group remains at desired capacity two.
- Verified the Lambda function was Active and the CloudFront site/API returned HTTP 200. Did not claim end-to-end user signup, CRUD, uploads, image queue execution, SNS delivery, Bedrock inference, load scaling, or SageMaker inference without observed evidence.
- SageMaker endpoint remains disabled to conserve the reported $100 in credits. The $30 monthly AWS Budget is an alert, not a cap; NAT, ALB, EC2, and CloudFront remain live and billable.
- Updated the rubric matrix, deployment guide, README, architecture, and cost notes to reflect actual deployed state and remaining verification. Generated and visually reviewed the submission report after deployment verification.
- Re-read the complete 11-page course specification and aligned the submission report with its deliverables and limitations.
- Added `scripts/seed_demo.py` and `docs/video-demo-guide.md` for a local-only presentation dataset (eight fictional listings and two notices). Verified the local API health response (HTTP 200), demo login (HTTP 200), and Vite frontend (HTTP 200); no AWS service was called for this demo data.
- Generated the three-page report PDF with an architecture diagram, service rationale, deployment checks, cost estimate, rubric coverage, remaining gaps, and cleanup instructions; rendered and visually inspected all three pages.
- The user reports that the demo video has been recorded; its file has not been provided in the workspace, so it is not included in the repository/report artifacts.
- The user later stopped one EC2 instance and reported no replacement. The AWS health check was interrupted before returning; no AWS changes were made during source cleanup. Recheck the Auto Scaling group before claiming current capacity is healthy.
(https://github.com/AwaisBasheer/CloudScale); p
