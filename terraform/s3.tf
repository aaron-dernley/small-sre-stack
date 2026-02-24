# ── S3 bucket for user avatars ───────────────────────────────────────────────

resource "aws_s3_bucket" "avatars" {
  bucket = var.project_name
  tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "avatars" {
  bucket = aws_s3_bucket.avatars.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "avatars" {
  bucket = aws_s3_bucket.avatars.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Allow public object reads so avatar URLs work without signing.
# In a stricter production environment this block should remain enabled and
# pre-signed URLs should be generated server-side instead.
resource "aws_s3_bucket_public_access_block" "avatars" {
  bucket = aws_s3_bucket.avatars.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "avatars_public_read" {
  bucket     = aws_s3_bucket.avatars.id
  depends_on = [aws_s3_bucket_public_access_block.avatars]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.avatars.arn}/*"
      }
    ]
  })
}

# aws_s3_bucket_lifecycle_configuration is intentionally omitted here.
# LocalStack CE does not fully implement the lifecycle API and causes Terraform
# to enter an infinite reconciliation loop on GetBucketLifecycleConfiguration.
# In a real AWS deployment, add a lifecycle rule to expire noncurrent object
# versions after 90 days to control storage costs on the versioned bucket.
