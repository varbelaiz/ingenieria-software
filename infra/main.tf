terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket       = "ing-soft-tf-state"
    key          = "ingenieria-software/terraform.tfstate"
    region       = "us-east-2"
    profile      = "universidad"
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}
