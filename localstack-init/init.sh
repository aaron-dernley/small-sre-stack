#!/bin/bash
# LocalStack initialisation script – runs once when LocalStack is ready.
# Creates the DynamoDB table and S3 bucket used by the API.

set -euo pipefail

REGION="${DEFAULT_REGION:-us-east-1}"
TABLE_NAME="${DYNAMODB_TABLE_NAME:-prima-tech-challenge-users}"
BUCKET_NAME="${S3_BUCKET_NAME:-prima-tech-challenge}"

echo ">>> Creating DynamoDB table: ${TABLE_NAME}"
awslocal dynamodb create-table \
    --table-name "${TABLE_NAME}" \
    --attribute-definitions AttributeName=email,AttributeType=S \
    --key-schema AttributeName=email,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}"

echo ">>> Creating S3 bucket: ${BUCKET_NAME}"
awslocal s3 mb "s3://${BUCKET_NAME}" --region "${REGION}"

# Allow public GET so avatar URLs work without credentials
echo ">>> Applying public-read bucket policy"
awslocal s3api put-bucket-policy \
    --bucket "${BUCKET_NAME}" \
    --policy "{
        \"Version\": \"2012-10-17\",
        \"Statement\": [{
            \"Sid\": \"PublicReadGetObject\",
            \"Effect\": \"Allow\",
            \"Principal\": \"*\",
            \"Action\": \"s3:GetObject\",
            \"Resource\": \"arn:aws:s3:::${BUCKET_NAME}/*\"
        }]
    }"

echo ">>> LocalStack init complete"
