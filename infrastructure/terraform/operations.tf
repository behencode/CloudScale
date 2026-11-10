resource "aws_cloudwatch_metric_alarm" "ec2_cpu" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "${var.project_name}-high-cpu"
  alarm_description   = "Average EC2 CPU is above 80% for two periods."
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app[0].name
  }
  alarm_actions = [aws_sns_topic.events[0].arn]
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count               = local.enabled ? 1 : 0
  alarm_name          = "${var.project_name}-image-worker-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  dimensions = {
    FunctionName = aws_lambda_function.image_processor[0].function_name
  }
  alarm_actions = [aws_sns_topic.events[0].arn]
}

resource "aws_cloudwatch_dashboard" "app" {
  count          = local.enabled ? 1 : 0
  dashboard_name = "${var.project_name}-operations"
  dashboard_body = jsonencode({
    widgets = [
      { type = "metric", x = 0, y = 0, width = 12, height = 6, properties = { region = var.aws_region, title = "ASG EC2 CPU", period = 300, stat = "Average", metrics = [["AWS/EC2", "CPUUtilization", "AutoScalingGroupName", aws_autoscaling_group.app[0].name]] } },
      { type = "metric", x = 12, y = 0, width = 12, height = 6, properties = { region = var.aws_region, title = "ALB requests and target latency", period = 60, stat = "Sum", metrics = [["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.app[0].arn_suffix], [".", "TargetResponseTime", ".", ".", { stat = "Average", yAxis = "right" }]] } },
      { type = "metric", x = 0, y = 6, width = 12, height = 6, properties = { region = var.aws_region, title = "Image Lambda invocations and errors", period = 300, stat = "Sum", metrics = [["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.image_processor[0].function_name], [".", "Errors", ".", "."]] } },
      { type = "metric", x = 12, y = 6, width = 12, height = 6, properties = { region = var.aws_region, title = "ALB healthy targets", period = 60, stat = "Average", metrics = [["AWS/ApplicationELB", "HealthyHostCount", "LoadBalancer", aws_lb.app[0].arn_suffix, "TargetGroup", aws_lb_target_group.app[0].arn_suffix]] } }
    ]
  })
}

resource "aws_budgets_budget" "monthly" {
  count        = local.enabled && var.budget_notification_email != "" ? 1 : 0
  provider     = aws.us_east_1
  name         = "${var.project_name}-monthly-cost"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_notification_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_notification_email]
  }
}

output "cloudfront_url" {
  description = "CloudFront URL; assets must be built before Terraform apply."
  value       = local.enabled ? "https://${aws_cloudfront_distribution.app[0].domain_name}" : null
}

output "s3_bucket" {
  value = local.enabled ? aws_s3_bucket.app[0].bucket : null
}

output "dynamodb_table" {
  value = local.enabled ? aws_dynamodb_table.app[0].name : null
}

output "cognito_user_pool_id" {
  value = local.enabled ? aws_cognito_user_pool.app[0].id : null
}

output "cognito_app_client_id" {
  value = local.enabled ? aws_cognito_user_pool_client.app[0].id : null
}
