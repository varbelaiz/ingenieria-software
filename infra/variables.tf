variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "instance_type" {
  description = "EC2 instance type for both API and monitoring"
  type        = string
  default     = "t3.micro"
}

variable "github_org" {
  description = "GitHub organization or username (e.g. varbelaiz)"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (e.g. ingenieria-software)"
  type        = string
}

variable "api_key" {
  description = "API key for the production application"
  type        = string
  sensitive   = true
}

variable "grafana_admin_password" {
  description = "Grafana admin password for the monitoring stack"
  type        = string
  sensitive   = true
}
