resource "aws_iam_role" "image_lambda" {
  count = local.enabled ? 1 : 0
  name  = "${var.project_name}-image-lambda"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_cloudwatch_log_group" "image_lambda" {
  count             = local.enabled ? 1 : 0
  name              = "/aws/lambda/${var.project_name}-image-processor"
  retention_in_days = 30
}

resource "aws_iam_role_policy" "image_lambda" {
  count = local.enabled ? 1 : 0
  name  = "${var.project_name}-image-worker"
  role  = aws_iam_role.image_lambda[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = ["${aws_cloudwatch_log_group.image_lambda[0].arn}:*"] },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${aws_s3_bucket.app[0].arn}/uploads/*"] },
      { Effect = "Allow", Action = ["s3:PutObject"], Resource = ["${aws_s3_bucket.app[0].arn}/processed/*"] },
      { Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = [aws_dynamodb_table.app[0].arn] },
      { Effect = "Allow", Action = ["sns:Publish"], Resource = [aws_sns_topic.events[0].arn] },
      { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = [aws_sqs_queue.images[0].arn] }
    ]
  })
}

resource "aws_lambda_function" "image_processor" {
  count            = local.enabled ? 1 : 0
  function_name    = "${var.project_name}-image-processor"
  role             = aws_iam_role.image_lambda[0].arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = 60
  memory_size      = 512
  environment {
    variables = {
      S3_BUCKET      = aws_s3_bucket.app[0].bucket
      DYNAMODB_TABLE = aws_dynamodb_table.app[0].name
      SNS_TOPIC_ARN  = aws_sns_topic.events[0].arn
    }
  }
  depends_on = [aws_cloudwatch_log_group.image_lambda]
}

resource "aws_lambda_event_source_mapping" "images" {
  count                              = local.enabled ? 1 : 0
  event_source_arn                   = aws_sqs_queue.images[0].arn
  function_name                      = aws_lambda_function.image_processor[0].arn
  batch_size                         = 5
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_batching_window_in_seconds = 5
}

resource "aws_iam_role" "sagemaker" {
  count = local.enabled && var.enable_sagemaker_endpoint ? 1 : 0
  name  = "${var.project_name}-sagemaker"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "sagemaker.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "sagemaker" {
  count = local.enabled && var.enable_sagemaker_endpoint ? 1 : 0
  name  = "${var.project_name}-model-artifact"
  role  = aws_iam_role.sagemaker[0].id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${aws_s3_bucket.app[0].arn}/${var.sagemaker_model_artifact_key}"] }]
  })
}

resource "aws_sagemaker_model" "category" {
  count              = local.enabled && var.enable_sagemaker_endpoint ? 1 : 0
  name               = "${var.project_name}-category-model"
  execution_role_arn = aws_iam_role.sagemaker[0].arn
  primary_container {
    image          = local.sagemaker_image
    model_data_url = "s3://${aws_s3_bucket.app[0].bucket}/${var.sagemaker_model_artifact_key}"
  }
  depends_on = [aws_iam_role_policy.sagemaker]
}

resource "aws_sagemaker_endpoint_configuration" "category" {
  count       = local.enabled && var.enable_sagemaker_endpoint ? 1 : 0
  name_prefix = "${var.project_name}-category-"
  production_variants {
    variant_name = "category"
    model_name   = aws_sagemaker_model.category[0].name
    serverless_config {
      max_concurrency   = 2
      memory_size_in_mb = var.sagemaker_memory_size_mb
    }
  }
  lifecycle { create_before_destroy = true }
}

resource "aws_sagemaker_endpoint" "category" {
  count                = local.enabled && var.enable_sagemaker_endpoint ? 1 : 0
  name                 = "${var.project_name}-category"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.category[0].name
}
