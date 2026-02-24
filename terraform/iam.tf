# ── IAM policies ──────────────────────────────────────────────────────────────

resource "aws_iam_policy" "s3_access" {
  name        = "${var.project_name}-s3-access"
  description = "Allows the API to read/write objects in the avatars S3 bucket."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ObjectOperations"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
        ]
        Resource = "${aws_s3_bucket.avatars.arn}/*"
      },
      {
        Sid      = "BucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.avatars.arn
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "dynamodb_access" {
  name        = "${var.project_name}-dynamodb-access"
  description = "Allows the API to read/write items in the users DynamoDB table."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TableOperations"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:Query",
        ]
        Resource = aws_dynamodb_table.users.arn
      }
    ]
  })

  tags = local.common_tags
}

# ── IAM role for the API workload ─────────────────────────────────────────────
#
# When eks_oidc_provider_arn is supplied the role uses IRSA (IAM Roles for
# Service Accounts) so the Kubernetes ServiceAccount can assume it without
# long-lived credentials.  When the variable is empty a standard EC2 trust
# policy is created instead (useful for LocalStack / non-EKS testing).

locals {
  use_irsa = var.eks_oidc_provider_arn != ""

  irsa_assume_role_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.eks_oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.eks_oidc_provider_url}:sub" = "system:serviceaccount:${var.k8s_namespace}:${var.k8s_service_account_name}"
            "${var.eks_oidc_provider_url}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  }

  # Fallback for non-EKS environments
  ec2_assume_role_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  }
}

resource "aws_iam_role" "prima_api" {
  name               = "${var.project_name}-api-role"
  assume_role_policy = local.use_irsa ? jsonencode(local.irsa_assume_role_policy) : jsonencode(local.ec2_assume_role_policy)
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "prima_api_s3" {
  role       = aws_iam_role.prima_api.name
  policy_arn = aws_iam_policy.s3_access.arn
}

resource "aws_iam_role_policy_attachment" "prima_api_dynamodb" {
  role       = aws_iam_role.prima_api.name
  policy_arn = aws_iam_policy.dynamodb_access.arn
}
