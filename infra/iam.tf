locals {
  is_prod = terraform.workspace == "prod"
}

# ─── OIDC: GitHub Actions (shared — only created in prod workspace) ──────────

data "tls_certificate" "github" {
  count = local.is_prod ? 1 : 0
  url   = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  count           = local.is_prod ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github[0].certificates[0].sha1_fingerprint]
}

resource "aws_iam_role" "github_actions" {
  count = local.is_prod ? 1 : 0
  name  = "github-actions-cd"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github[0].arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main",
            "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/develop"
          ]
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_actions" {
  count = local.is_prod ? 1 : 0
  name  = "github-actions-cd-policy"
  role  = aws_iam_role.github_actions[0].id

  # Wildcard api-* covers both api-prod and api-staging ECR repos,
  # since staging is applied in a different workspace and its ARN is not
  # available here at plan time.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "arn:aws:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/api-*"
      },
      {
        Sid      = "SSMDeploy"
        Effect   = "Allow"
        Action   = ["ssm:SendCommand", "ssm:GetCommandInvocation"]
        Resource = "*"
      }
    ]
  })
}

# ─── EC2 Instance Profile (per workspace) ────────────────────────────────────

resource "aws_iam_role" "app" {
  name = "ec2-app-${terraform.workspace}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "app_ssm" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "app" {
  name = "ec2-app-${terraform.workspace}-policy"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability"
        ]
        Resource = aws_ecr_repository.api.arn
      },
      {
        Sid      = "SecretsManagerRead"
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = [
          aws_secretsmanager_secret.api_key.arn,
          aws_secretsmanager_secret.grafana_admin_password.arn
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "app" {
  name = "ec2-app-${terraform.workspace}"
  role = aws_iam_role.app.name
}
