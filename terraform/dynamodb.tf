# ── DynamoDB table for user records ──────────────────────────────────────────

resource "aws_dynamodb_table" "users" {
  name         = "${var.project_name}-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email"

  attribute {
    name = "email"
    type = "S"
  }

  # Enable Point-in-Time Recovery for data durability
  point_in_time_recovery {
    enabled = true
  }

  # Encryption at rest using AWS-managed keys.
  # SSE is omitted when targeting LocalStack (KMS not available in CE);
  # real AWS enables SSE by default on all DynamoDB tables regardless.
  dynamic "server_side_encryption" {
    for_each = var.localstack_endpoint == "" ? [1] : []
    content {
      enabled = true
    }
  }

  tags = local.common_tags
}
