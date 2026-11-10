# Cost analysis

## Current state

The AWS stack is live in us-east-1. The Terraform default in source still disables resource creation; the ignored local tfvars enables the current account deployment. Cost Explorer is unavailable to the active identity, so actual spend was not observed. The user reports $100 in credits. A $30 monthly budget sends alerts at 80% and 100%; it does not cap spend or stop resources.

## Cost drivers to evaluate before deployment

| Service / resource | Main cost drivers |
|---|---|
| EC2, Auto Scaling, load balancer | Instance hours, load balancer hours and capacity units, EBS, and data transfer. |
| NAT Gateway | Gateway hours plus processed data; usually a significant fixed cost for a small deployment. |
| S3 and CloudFront | Stored and versioned image bytes, requests, cache invalidations, and outbound transfer. |
| DynamoDB | On-demand requests or provisioned capacity, stored data, backups, and streams if enabled. |
| SQS and SNS | Request volume, payload size, delivery protocol, and retries. |
| Lambda | Invocations, duration, memory, and data transfer. |
| Cognito | Monthly active users and enabled authentication features. |
| Bedrock | Model and token usage, varying by model and region. |
| SageMaker endpoint | Instance type and continuously provisioned endpoint hours, including idle time. |
| Route 53 and CloudWatch | Hosted zones and queries; metrics, logs ingestion, retention, dashboards, and alarms. |

For the deployed shape, the always-on baseline is roughly $2-$3/day before variable data, request, and model charges: one NAT Gateway, one ALB, two small EC2 instances, public IPv4 addresses, CloudFront, and associated storage/logging. This is a rough planning estimate; actual rates and usage depend on region and traffic. AWS pricing references: [VPC](https://aws.amazon.com/vpc/pricing/), [ALB](https://aws.amazon.com/elasticloadbalancing/pricing/), and [T3 EC2](https://aws.amazon.com/ec2/instance-types/t3/). SageMaker endpoint hours are avoided because the endpoint is disabled.

## Cost controls

- Keep local provider defaults during development.
- Set service-specific choices explicitly and review `GET /api/health` warnings.
- Use budgets and billing alerts in the AWS account before testing integrations.
- Prefer short-lived or on-demand compute where suitable; remove unused resources through a reviewed change.
- Use S3 lifecycle rules and bounded log retention, with retention chosen to meet operational needs.
- Never assume `APP_MODE=local` prevents charges if an AWS provider has separately been selected.
- When the demo is no longer needed, review and run `terraform destroy` promptly; the NAT Gateway, ALB, and EC2 instances continue to incur hourly charges while the stack remains online.
