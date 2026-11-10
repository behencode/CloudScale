variable "project_name" {
  description = "Lowercase project name used as the prefix for resources."
  type        = string
  default     = "campusconnect"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name must be 3-21 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "aws_region" {
  description = "AWS region for the VPC, application, and regional services."
  type        = string
  default     = "us-east-1"
}

variable "cloudfront_origin_prefix_list_id" {
  description = "AWS managed CloudFront origin-facing prefix list ID for aws_region. Verify it when changing regions."
  type        = string
  default     = "pl-3b927c52"
}

variable "enable_paid_infrastructure" {
  description = "Master switch. When false, Terraform creates no AWS resources. Set true only after reviewing costs and the plan."
  type        = bool
  default     = false
}

variable "instance_type" {
  description = "EC2 instance type for the private API Auto Scaling Group."
  type        = string
  default     = "t3.micro"
}

variable "lambda_package_path" {
  description = "Optional absolute path to the image-processor zip. Empty uses infrastructure/terraform/.build/image_processor.zip from scripts/package_lambda.sh."
  type        = string
  default     = ""
}

variable "enable_nat_gateway" {
  description = "Create one NAT Gateway for outbound package installation from private EC2 instances."
  type        = bool
  default     = true
}

variable "enable_sagemaker_endpoint" {
  description = "Create the optional SageMaker Serverless Inference endpoint. Requires a trained model artifact in the project bucket."
  type        = bool
  default     = false
}

variable "sagemaker_model_artifact_key" {
  description = "S3 key for the trained SageMaker model.tar.gz artifact."
  type        = string
  default     = "models/category/model.tar.gz"
}

variable "sagemaker_inference_image_uri" {
  description = "SageMaker scikit-learn inference container image URI for the selected region and framework version."
  type        = string
  default     = ""
}

variable "sagemaker_memory_size_mb" {
  description = "Memory for the serverless category endpoint."
  type        = number
  default     = 2048
  validation {
    condition     = contains([1024, 2048, 3072, 4096, 5120, 6144], var.sagemaker_memory_size_mb)
    error_message = "SageMaker Serverless memory must be 1024-6144 MB in 1024 MB steps."
  }
}

variable "bedrock_model_id" {
  description = "Foundation model or inference profile used by the listing description generator."
  type        = string
  default     = "us.amazon.nova-micro-v1:0"
}

variable "hosted_zone_id" {
  description = "Existing public Route 53 hosted zone ID. Leave empty to use the CloudFront default domain."
  type        = string
  default     = ""
}

variable "app_domain" {
  description = "Optional DNS name within hosted_zone_id, for example board.example.edu."
  type        = string
  default     = ""
  validation {
    condition     = var.app_domain == "" || (var.hosted_zone_id != "" && var.cloudfront_certificate_arn != "")
    error_message = "A custom app_domain requires an existing hosted_zone_id and a validated CloudFront ACM certificate ARN from us-east-1."
  }
}

variable "cloudfront_certificate_arn" {
  description = "Optional issued ACM certificate ARN in us-east-1 covering app_domain."
  type        = string
  default     = ""
}

variable "budget_limit_usd" {
  description = "Monthly cost budget in USD; choose a limit consistent with the actual account credits."
  type        = number
  default     = 50
  validation {
    condition     = var.budget_limit_usd > 0
    error_message = "budget_limit_usd must be positive."
  }
}

variable "budget_notification_email" {
  description = "Email recipient for 80% and 100% actual cost budget alerts."
  type        = string
  default     = ""
}

variable "notification_email" {
  description = "Optional email subscription for SNS listing events and CloudWatch alarms."
  type        = string
  default     = ""
}

variable "bedrock_model_arn" {
  description = "IAM resource ARN for the approved Bedrock model or inference profile."
  type        = string
  default     = "arn:aws:bedrock:us-east-1::inference-profile/us.amazon.nova-micro-v1:0"
}
