terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote backend example (uncomment for production):
  # backend "s3" {
  #   bucket         = "my-terraform-state"
  #   key            = "prima-sre-task/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-state-lock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  # LocalStack compatibility – skip real-AWS checks when an endpoint is set.
  dynamic "endpoints" {
    for_each = var.localstack_endpoint != "" ? [1] : []
    content {
      dynamodb = var.localstack_endpoint
      iam      = var.localstack_endpoint
      s3       = var.localstack_endpoint
      sts      = var.localstack_endpoint
    }
  }

  skip_credentials_validation = var.localstack_endpoint != ""
  skip_requesting_account_id  = var.localstack_endpoint != ""
  skip_metadata_api_check     = var.localstack_endpoint != ""
  s3_use_path_style           = var.localstack_endpoint != ""

  # Dummy credentials for LocalStack (ignored on real AWS)
  access_key = var.localstack_endpoint != "" ? "test" : null
  secret_key = var.localstack_endpoint != "" ? "test" : null
}
