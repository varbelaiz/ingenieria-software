output "app_public_ip" {
  description = "Public IP of the app EC2 instance for this workspace"
  value       = aws_instance.app.public_ip
}

output "urls" {
  description = "Public URLs for this environment"
  value = {
    api        = "http://${aws_instance.app.public_ip}:8000"
    grafana    = "http://${aws_instance.app.public_ip}:3000"
    prometheus = "http://${aws_instance.app.public_ip}:9090"
  }
}

output "ecr_registry" {
  description = "ECR registry URL — set as ECR_REGISTRY GitHub secret"
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}

output "ecr_repository" {
  description = "ECR repository name for this workspace"
  value       = aws_ecr_repository.api.name
}

output "github_actions_role_arn" {
  description = "ARN of the shared GitHub Actions IAM role (only set when running in prod workspace)"
  value       = local.is_prod ? aws_iam_role.github_actions[0].arn : null
}
