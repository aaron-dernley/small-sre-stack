output "s3_bucket_name" {
  description = "Name of the S3 bucket that stores avatars."
  value       = aws_s3_bucket.avatars.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 avatar bucket."
  value       = aws_s3_bucket.avatars.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB users table."
  value       = aws_dynamodb_table.users.id
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB users table."
  value       = aws_dynamodb_table.users.arn
}

output "api_iam_role_arn" {
  description = "ARN of the IAM role assumed by the API workload (use as IRSA annotation)."
  value       = aws_iam_role.prima_api.arn
}
