locals {
  enabled  = var.enable_paid_infrastructure
  az_names = try(data.aws_availability_zones.available[0].names, [])
  azs      = length(local.az_names) >= 2 ? slice(local.az_names, 0, 2) : []
  public_subnets = { for i, az in local.azs : tostring(i) => {
    az = az, cidr = cidrsubnet("10.0.0.0/16", 8, i)
  } }
  private_subnets = { for i, az in local.azs : tostring(i) => {
    az = az, cidr = cidrsubnet("10.0.0.0/16", 8, i + 16)
  } }
  sklearn_images = {
    us-east-1 = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1"
  }
  sagemaker_image         = var.sagemaker_inference_image_uri != "" ? var.sagemaker_inference_image_uri : lookup(local.sklearn_images, var.aws_region, "")
  category_provider       = var.enable_sagemaker_endpoint ? "sagemaker" : "local"
  sagemaker_endpoint_name = var.enable_sagemaker_endpoint ? aws_sagemaker_endpoint.category[0].name : ""
  app_origin              = var.app_domain != "" ? "https://${var.app_domain}" : (local.enabled ? "https://${aws_cloudfront_distribution.app[0].domain_name}" : "http://localhost:5173")
  frontend_files          = local.enabled ? fileset("${path.module}/../../frontend/dist", "**") : toset([])
  lambda_zip              = var.lambda_package_path != "" ? var.lambda_package_path : "${path.module}/.build/image_processor.zip"
  content_types = {
    css  = "text/css"
    html = "text/html"
    js   = "text/javascript"
    json = "application/json"
    map  = "application/json"
    png  = "image/png"
    svg  = "image/svg+xml"
    txt  = "text/plain"
    ico  = "image/x-icon"
  }
}

check "paid_stack_is_reviewable" {
  assert {
    condition     = !var.enable_paid_infrastructure || var.enable_nat_gateway
    error_message = "Set enable_nat_gateway=true with enable_paid_infrastructure. Private instances cannot install packages or reach Bedrock, SQS, SNS, or SageMaker without it."
  }
  assert {
    condition     = !var.enable_paid_infrastructure || var.budget_notification_email != ""
    error_message = "Set budget_notification_email before creating paid infrastructure so the AWS Budget has a recipient."
  }
  assert {
    condition     = !var.enable_sagemaker_endpoint || local.sagemaker_image != ""
    error_message = "Set sagemaker_inference_image_uri. No default scikit-learn image is recorded for this region."
  }
}

data "aws_availability_zones" "available" {
  count = local.enabled ? 1 : 0
  state = "available"
}

data "aws_ami" "al2023" {
  count       = local.enabled ? 1 : 0
  owners      = ["amazon"]
  most_recent = true
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-kernel-*-x86_64"]
  }
  filter {
    name   = "state"
    values = ["available"]
  }
}

data "aws_caller_identity" "current" {
  count = local.enabled ? 1 : 0
}

data "archive_file" "backend" {
  count       = local.enabled ? 1 : 0
  type        = "zip"
  source_dir  = "${path.module}/../../backend"
  output_path = "${path.module}/backend-bundle.zip"
  excludes    = [".venv/**", "tests/**", "data/**", "**/__pycache__/**", "**/*.pyc", "pytest.ini"]
}

resource "aws_vpc" "main" {
  count                = local.enabled ? 1 : 0
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  count  = local.enabled ? 1 : 0
  vpc_id = aws_vpc.main[0].id
  tags   = { Name = "${var.project_name}-igw" }
}

resource "aws_subnet" "public" {
  for_each                = local.public_subnets
  vpc_id                  = aws_vpc.main[0].id
  availability_zone       = each.value.az
  cidr_block              = each.value.cidr
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project_name}-public-${each.key}", Tier = "public" }
}

resource "aws_subnet" "private" {
  for_each          = local.private_subnets
  vpc_id            = aws_vpc.main[0].id
  availability_zone = each.value.az
  cidr_block        = each.value.cidr
  tags              = { Name = "${var.project_name}-private-${each.key}", Tier = "private" }
}

resource "aws_route_table" "public" {
  count  = local.enabled ? 1 : 0
  vpc_id = aws_vpc.main[0].id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }
}

resource "aws_route_table_association" "public" {
  for_each       = local.public_subnets
  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_eip" "nat" {
  count      = local.enabled && var.enable_nat_gateway ? 1 : 0
  domain     = "vpc"
  depends_on = [aws_internet_gateway.main]
}

resource "aws_nat_gateway" "main" {
  count         = local.enabled && var.enable_nat_gateway ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public["0"].id
  depends_on    = [aws_internet_gateway.main]
  tags          = { Name = "${var.project_name}-nat" }
}

resource "aws_route_table" "private" {
  count  = local.enabled ? 1 : 0
  vpc_id = aws_vpc.main[0].id
}

resource "aws_route" "private_nat" {
  count                  = local.enabled && var.enable_nat_gateway ? 1 : 0
  route_table_id         = aws_route_table.private[0].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[0].id
}

resource "aws_route_table_association" "private" {
  for_each       = local.private_subnets
  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = aws_route_table.private[0].id
}

resource "aws_vpc_endpoint" "s3" {
  count             = local.enabled ? 1 : 0
  vpc_id            = aws_vpc.main[0].id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private[0].id]
}

resource "aws_vpc_endpoint" "dynamodb" {
  count             = local.enabled ? 1 : 0
  vpc_id            = aws_vpc.main[0].id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private[0].id]
}

resource "aws_s3_bucket" "app" {
  count         = local.enabled ? 1 : 0
  bucket_prefix = "${var.project_name}-"
}

resource "aws_s3_bucket_public_access_block" "app" {
  count                   = local.enabled ? 1 : 0
  bucket                  = aws_s3_bucket.app[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.app[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "app" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.app[0].id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "app" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.app[0].id
  rule {
    id     = "retain-and-tier-older-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }
    noncurrent_version_expiration { noncurrent_days = 365 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
  depends_on = [aws_s3_bucket_versioning.app]
}

resource "aws_s3_object" "backend_bundle" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.app[0].id
  key    = "deploy/backend.zip"
  source = data.archive_file.backend[0].output_path
  etag   = filemd5(data.archive_file.backend[0].output_path)
}

resource "aws_dynamodb_table" "app" {
  count        = local.enabled ? 1 : 0
  name         = "${var.project_name}-data"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"
  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  attribute {
    name = "gsi2pk"
    type = "S"
  }
  attribute {
    name = "gsi2sk"
    type = "S"
  }
  attribute {
    name = "gsi3pk"
    type = "S"
  }
  attribute {
    name = "gsi3sk"
    type = "S"
  }
  attribute {
    name = "gsi4pk"
    type = "S"
  }
  attribute {
    name = "gsi4sk"
    type = "S"
  }
  global_secondary_index {
    name            = "listings-by-time"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "listings-by-category"
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "listings-by-owner"
    hash_key        = "gsi3pk"
    range_key       = "gsi3sk"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "users-by-email"
    hash_key        = "gsi4pk"
    range_key       = "gsi4sk"
    projection_type = "ALL"
  }
  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
}

resource "aws_sqs_queue" "dlq" {
  count                     = local.enabled ? 1 : 0
  name                      = "${var.project_name}-images-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "images" {
  count                      = local.enabled ? 1 : 0
  name                       = "${var.project_name}-images"
  visibility_timeout_seconds = 360
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[0].arn
    maxReceiveCount     = 4
  })
}

resource "aws_sns_topic" "events" {
  count             = local.enabled ? 1 : 0
  name              = "${var.project_name}-events"
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_sns_topic_subscription" "email" {
  count     = local.enabled && var.notification_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.events[0].arn
  protocol  = "email"
  endpoint  = var.notification_email
}

resource "aws_cognito_user_pool" "app" {
  count                    = local.enabled ? 1 : 0
  name                     = "${var.project_name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }
  schema {
    name                = "name"
    attribute_data_type = "String"
    required            = false
    mutable             = true
  }
}

resource "aws_cognito_user_pool_client" "app" {
  count                         = local.enabled ? 1 : 0
  name                          = "${var.project_name}-web"
  user_pool_id                  = aws_cognito_user_pool.app[0].id
  generate_secret               = false
  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
  access_token_validity         = 60
  id_token_validity             = 60
  refresh_token_validity        = 7
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "random_password" "origin_header" {
  count   = local.enabled ? 1 : 0
  length  = 40
  special = false
}

resource "aws_cloudfront_origin_access_control" "assets" {
  count                             = local.enabled ? 1 : 0
  name                              = "${var.project_name}-assets"
  description                       = "Private frontend assets access"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_response_headers_policy" "security" {
  count = local.enabled ? 1 : 0
  name  = "${var.project_name}-security-headers"
  security_headers_config {
    content_type_options { override = true }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
  }
}

resource "aws_cloudfront_distribution" "app" {
  count               = local.enabled ? 1 : 0
  enabled             = true
  default_root_object = "index.html"
  aliases             = var.app_domain != "" ? [var.app_domain] : []
  price_class         = "PriceClass_100"
  origin {
    domain_name              = aws_s3_bucket.app[0].bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_path              = "/frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.assets[0].id
  }
  origin {
    domain_name = aws_lb.app[0].dns_name
    origin_id   = "api-alb"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
    custom_header {
      name  = "X-CloudScale-Origin"
      value = random_password.origin_header[0].result
    }
  }
  default_cache_behavior {
    target_origin_id           = "frontend-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security[0].id
    compress                   = true
  }
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "api-alb"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Content-Type", "Origin"]
      cookies { forward = "all" }
    }
    min_ttl                    = 0
    default_ttl                = 0
    max_ttl                    = 0
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security[0].id
  }
  ordered_cache_behavior {
    path_pattern           = "/uploads/*"
    target_origin_id       = "api-alb"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    forwarded_values {
      query_string = true
      headers      = ["Origin"]
      cookies {
        forward = "none"
      }
    }
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }
  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate {
    cloudfront_default_certificate = var.cloudfront_certificate_arn == ""
    acm_certificate_arn            = var.cloudfront_certificate_arn != "" ? var.cloudfront_certificate_arn : null
    ssl_support_method             = var.cloudfront_certificate_arn != "" ? "sni-only" : null
    minimum_protocol_version       = var.cloudfront_certificate_arn != "" ? "TLSv1.2_2021" : null
  }
}

resource "aws_s3_bucket_policy" "app" {
  count  = local.enabled ? 1 : 0
  bucket = aws_s3_bucket.app[0].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Sid = "CloudFrontReadFrontend", Effect = "Allow", Principal = { Service = "cloudfront.amazonaws.com" }, Action = "s3:GetObject", Resource = "${aws_s3_bucket.app[0].arn}/frontend/*", Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.app[0].arn } } },
    { Sid = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.app[0].arn, "${aws_s3_bucket.app[0].arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } } }
  ] })
}

resource "aws_s3_object" "frontend" {
  for_each     = local.frontend_files
  bucket       = aws_s3_bucket.app[0].id
  key          = "frontend/${each.value}"
  source       = "${path.module}/../../frontend/dist/${each.value}"
  etag         = filemd5("${path.module}/../../frontend/dist/${each.value}")
  content_type = lookup(local.content_types, reverse(split(".", each.value))[0], "application/octet-stream")
}
