# Deployment guide

## Current status

CampusConnect is deployed in us-east-1 at [https://d39xic7jvhqh80.cloudfront.net](https://d39xic7jvhqh80.cloudfront.net). The API `/api/health` returns HTTP 200 with no warnings. Cognito is selected for authentication; DynamoDB and S3 are selected for persistence and storage; Bedrock is selected for descriptions; category suggestions use the local provider; notifications use AWS. The Auto Scaling group has desired capacity 2 and both ALB targets are healthy. A refresh was cancelled at 50% after AWS continued to report insufficient health data; the group is stable with two healthy instances. Cost Explorer is unavailable to the deployment identity. The user reports $100 in credits; SageMaker is disabled. The $30 monthly budget creates alerts at 80% and 100%; it is not a cap.

## Local run

Follow the commands in the repository [README](../README.md). Keep every provider at its local default for offline development. The frontend dev server proxies API and uploads to `127.0.0.1:8000`.

## AWS integration prerequisites

Before selecting any AWS-backed setting, provision the corresponding resource and least-privilege role, configure credentials through an AWS profile or the runtime role, and supply the resource identifiers in `backend/.env`. Required identifiers include:

| Setting | Resource / purpose |
|---|---|
| `DYNAMODB_TABLE` | Table with `pk`/`sk` and four GSIs described in `backend/app/dynamodb_repo.py`. The email index must expose the user profile key. |
| `S3_BUCKET` | Image storage bucket; the app uploads JPEG data and generates presigned URLs. |
| `SQS_QUEUE_URL` | Queue consumed by the image worker when image notifications are enabled. Configure a DLQ and partial batch response handling. |
| `SNS_TOPIC_ARN` | Listing event topic used by the AWS notifier and optionally the worker. |
| `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `COGNITO_REGION` | User pool and public app client configured for the browser's `USER_PASSWORD_AUTH` flow. |
| `BEDROCK_MODEL_ID` | Model or inference profile allowed in the selected region. |
| `SAGEMAKER_ENDPOINT_NAME` | Deployed endpoint accepting the JSON text payload expected by `SageMakerCategoryService`. |

Set only the relevant provider to `aws`, `s3`, `cognito`, `bedrock`, or `sagemaker` after validating resource names and IAM access. These options make live AWS calls and can incur charges. `APP_MODE=aws` alone does not switch providers.

## Remaining verification

- Complete one end-to-end Cognito signup and email confirmation using an authorized test address.
- Exercise listing CRUD, upload, SQS/Lambda image processing, SNS delivery, and a real Bedrock request against the live stack.
- SageMaker model training and endpoint deployment were deliberately omitted to conserve credits; local category suggestions remain active.
- No custom Route 53 domain, demo video, GitHub remote/collaborator setup, or teardown evidence is included.
- After grading, remove the temporary deployment policy through an AWS administrator and destroy billable infrastructure if the demo no longer needs to stay online.

## Staged deployment

1. Create a private state backend with encryption and locking, or use local state only for a disposable course environment. Do not commit Terraform state or `.tfvars`.
2. Run `terraform init`, `terraform fmt -check -recursive`, and `terraform validate` from `infrastructure/terraform`.
3. Set `enable_paid_infrastructure=true`, `budget_notification_email`, `budget_limit_usd`, and `enable_nat_gateway=true` in a private tfvars file. Keep SageMaker disabled for the first apply so the bucket and account resources exist before model training.
4. Build an initial `frontend/dist` using `cd frontend && npm ci && npm run build`, then create the Lambda package with `scripts/package_lambda.sh`.
5. Attach `infrastructure/terraform/deployer-policy.json` to a dedicated temporary deployment identity using an AWS account administrator, configure a named AWS CLI profile, and verify it with `aws sts get-caller-identity`. Use that profile for `terraform plan` and `terraform apply`. The JSON grants broad service power in us-east-1 and scoped management of `campusconnect-*` IAM roles; remove it after deployment and reattach only when Terraform changes or destroys the stack. Root credentials do not need to be shared.
6. Confirm the AWS Budget email, alarm topic subscription, Cognito email verification, CloudFront behavior, and private targets.
7. Read the Terraform outputs, export `VITE_COGNITO_REGION` and `VITE_COGNITO_CLIENT_ID`, run `scripts/build_frontend.sh`, then apply again to upload the Cognito-configured frontend assets.
8. Train and upload the category model artifact to `s3://<bucket>/models/category/model.tar.gz`, set `enable_sagemaker_endpoint=true` and the region's scikit-learn inference image URI, review the second plan, and apply. The endpoint is metered while provisioned; keep it disabled for this $100-credit deployment unless there is sufficient remaining credit.
9. Run `scripts/load_test.sh https://<cloudfront-domain>` and record CloudWatch scaling activities and target health. Record the end-to-end auth, listing, image, queue, Lambda, SNS, and Bedrock behavior.
10. After grading evidence is captured, run a reviewed `terraform destroy` and retain screenshots proving billable resources are terminated.

The deployed infrastructure includes a DynamoDB table (chosen for keyed listing/profile access and on-demand capacity), a gateway VPC endpoint for private access, S3 versioning/lifecycle, Cognito, a private EC2 ASG behind an ALB, CloudFront, SQS/DLQ/Lambda, SNS, CloudWatch dashboard/alarms, and budget alerts. SageMaker remains optional and disabled. The model artifact and region-specific inference image are operator-provided. Bedrock uses the real `Converse` API from the backend, but live inference has not been verified.

The browser uses Cognito `SignUp` and `ConfirmSignUp`; confirm the email flow against the deployed user pool before claiming end-to-end authentication is verified.
