resource "aws_security_group" "alb" {
  count       = local.enabled ? 1 : 0
  name        = "${var.project_name}-alb"
  description = "CloudFront-only traffic to the public load balancer"
  vpc_id      = aws_vpc.main[0].id
}

resource "aws_security_group" "app" {
  count       = local.enabled ? 1 : 0
  name        = "${var.project_name}-app"
  description = "Private CampusConnect API instances"
  vpc_id      = aws_vpc.main[0].id
}

resource "aws_vpc_security_group_ingress_rule" "alb_cloudfront" {
  count             = local.enabled ? 1 : 0
  security_group_id = aws_security_group.alb[0].id
  description       = "CloudFront origin-facing addresses only"
  prefix_list_id    = var.cloudfront_origin_prefix_list_id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app" {
  count                        = local.enabled ? 1 : 0
  security_group_id            = aws_security_group.alb[0].id
  referenced_security_group_id = aws_security_group.app[0].id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  count                        = local.enabled ? 1 : 0
  security_group_id            = aws_security_group.app[0].id
  referenced_security_group_id = aws_security_group.alb[0].id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_egress_rule" "app_egress" {
  count             = local.enabled ? 1 : 0
  security_group_id = aws_security_group.app[0].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_lb" "app" {
  count              = local.enabled ? 1 : 0
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb[0].id]
  subnets            = [for subnet in values(aws_subnet.public) : subnet.id]
}

resource "aws_lb_target_group" "app" {
  count       = local.enabled ? 1 : 0
  name        = "${var.project_name}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main[0].id
  target_type = "instance"
  health_check {
    path                = "/api/health"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  count             = local.enabled ? 1 : 0
  load_balancer_arn = aws_lb.app[0].arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Access through the CloudFront distribution."
      status_code  = "403"
    }
  }
}

resource "aws_lb_listener_rule" "cloudfront_origin" {
  count        = local.enabled ? 1 : 0
  listener_arn = aws_lb_listener.http[0].arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app[0].arn
  }
  condition {
    http_header {
      http_header_name = "X-CloudScale-Origin"
      values           = [random_password.origin_header[0].result]
    }
  }
}

resource "aws_iam_role" "ec2" {
  count = local.enabled ? 1 : 0
  name  = "${var.project_name}-ec2"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  count = local.enabled ? 1 : 0
  name  = "${var.project_name}-ec2"
  role  = aws_iam_role.ec2[0].name
}

resource "aws_iam_role_policy" "ec2" {
  count = local.enabled ? 1 : 0
  name  = "${var.project_name}-runtime"
  role  = aws_iam_role.ec2[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${aws_s3_bucket.app[0].arn}/deploy/backend.zip", "${aws_s3_bucket.app[0].arn}/uploads/*", "${aws_s3_bucket.app[0].arn}/processed/*"] },
      { Effect = "Allow", Action = ["s3:PutObject", "s3:DeleteObject"], Resource = ["${aws_s3_bucket.app[0].arn}/uploads/*", "${aws_s3_bucket.app[0].arn}/processed/*"] },
      { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem"], Resource = [aws_dynamodb_table.app[0].arn, "${aws_dynamodb_table.app[0].arn}/index/*"] },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = [aws_sqs_queue.images[0].arn] },
      { Effect = "Allow", Action = ["sns:Publish"], Resource = [aws_sns_topic.events[0].arn] },
      { Effect = "Allow", Action = ["bedrock:InvokeModel"], Resource = [var.bedrock_model_arn] },
      {
        Effect   = "Allow"
        Action   = ["sagemaker:InvokeEndpoint"]
        Resource = var.enable_sagemaker_endpoint ? [aws_sagemaker_endpoint.category[0].arn] : ["arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:endpoint/${var.project_name}-category"]
      }
    ]
  })
}

resource "aws_launch_template" "app" {
  count                  = local.enabled ? 1 : 0
  name_prefix            = "${var.project_name}-"
  image_id               = data.aws_ami.al2023[0].id
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.app[0].id]
  iam_instance_profile { name = aws_iam_instance_profile.ec2[0].name }
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  credit_specification { cpu_credits = "standard" }
  user_data = base64encode(templatefile("${path.module}/templates/user_data.sh.tftpl", {
    aws_region              = var.aws_region
    bucket_name             = aws_s3_bucket.app[0].bucket
    bundle_key              = aws_s3_object.backend_bundle[0].key
    table_name              = aws_dynamodb_table.app[0].name
    topic_arn               = aws_sns_topic.events[0].arn
    queue_url               = aws_sqs_queue.images[0].url
    user_pool_id            = aws_cognito_user_pool.app[0].id
    user_pool_client_id     = aws_cognito_user_pool_client.app[0].id
    bedrock_model_id        = var.bedrock_model_id
    category_provider       = local.category_provider
    sagemaker_endpoint_name = local.sagemaker_endpoint_name
    cors_origins            = local.app_origin
  }))
  depends_on = [aws_iam_role_policy.ec2]
  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.project_name}-api" }
  }
}

resource "aws_autoscaling_group" "app" {
  count                     = local.enabled ? 1 : 0
  name                      = "${var.project_name}-api"
  min_size                  = 2
  desired_capacity          = 2
  max_size                  = 4
  vpc_zone_identifier       = [for subnet in values(aws_subnet.private) : subnet.id]
  target_group_arns         = [aws_lb_target_group.app[0].arn]
  health_check_type         = "ELB"
  health_check_grace_period = 420
  launch_template {
    id      = aws_launch_template.app[0].id
    version = aws_launch_template.app[0].latest_version
  }
  instance_refresh {
    strategy = "Rolling"
    preferences { min_healthy_percentage = 50 }
  }
  lifecycle { create_before_destroy = true }
}

resource "aws_autoscaling_policy" "cpu" {
  count                  = local.enabled ? 1 : 0
  name                   = "${var.project_name}-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.app[0].name
  policy_type            = "TargetTrackingScaling"
  target_tracking_configuration {
    target_value = 60
    predefined_metric_specification { predefined_metric_type = "ASGAverageCPUUtilization" }
  }
}

resource "aws_route53_record" "app" {
  count   = local.enabled && var.hosted_zone_id != "" && var.app_domain != "" ? 1 : 0
  zone_id = var.hosted_zone_id
  name    = var.app_domain
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.app[0].domain_name
    zone_id                = aws_cloudfront_distribution.app[0].hosted_zone_id
    evaluate_target_health = false
  }
}
