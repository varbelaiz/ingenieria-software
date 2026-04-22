locals {
  git_branch = terraform.workspace == "prod" ? "main" : "develop"
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.app.name
  vpc_security_group_ids = [aws_security_group.app.id]

  user_data = templatefile("${path.module}/user_data/app.sh.tpl", {
    region       = var.region
    env_name     = terraform.workspace
    branch       = local.git_branch
    github_org   = var.github_org
    github_repo  = var.github_repo
    ecr_registry = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
    ecr_repo     = aws_ecr_repository.api.name
    secret_name  = aws_secretsmanager_secret.api_key.name
  })

  tags = {
    Name        = "app-${terraform.workspace}"
    Environment = terraform.workspace
  }
}
