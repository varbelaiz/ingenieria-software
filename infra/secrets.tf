resource "aws_secretsmanager_secret" "api_key" {
  name                    = "api/api-key-${terraform.workspace}"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id     = aws_secretsmanager_secret.api_key.id
  secret_string = var.api_key
}
