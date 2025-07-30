# 🗑️ Uninstall Guide - Complete Removal of RAG Chatbot

This guide provides comprehensive instructions for completely removing the RAG Chatbot solution and all associated AWS resources.

## ⚠️ Important Warning

**Uninstalling will permanently delete:**
- All uploaded documents and their embeddings
- Chat history and analytics data
- All AWS infrastructure resources
- Configuration and deployment state

**This action cannot be undone. Ensure you have backups of any important data.**

## 🚀 Quick Uninstall (Recommended)

If you deployed using the standard deployment script, use the built-in rollback feature:

```bash
# Navigate to your project directory
cd chatbot-rag-v1.0

# Perform automatic rollback/uninstall
./deploy.sh rollback
```

This will:
- ✅ Delete the CloudFormation stack and all AWS resources
- ✅ Clean up local deployment artifacts
- ✅ Remove temporary files and state

## 📋 Manual Uninstall Process

If the automatic rollback fails or you need to manually remove resources, follow these steps:

### Step 1: Delete CloudFormation Stack

```bash
# Delete the main infrastructure stack
aws cloudformation delete-stack --stack-name ChatbotRagStack

# Wait for deletion to complete (this may take 5-10 minutes)
aws cloudformation wait stack-delete-complete --stack-name ChatbotRagStack

# Verify stack is deleted
aws cloudformation describe-stacks --stack-name ChatbotRagStack
# Should return: "Stack with id ChatbotRagStack does not exist"
```

### Step 2: Clean Up S3 Buckets (If Not Auto-Deleted)

The CDK stack should automatically delete S3 buckets, but if they remain:

```bash
# Get your AWS account ID and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

# Delete document bucket contents and bucket
aws s3 rm s3://chatbot-documents-${ACCOUNT_ID}-${REGION} --recursive
aws s3 rb s3://chatbot-documents-${ACCOUNT_ID}-${REGION}

# Delete vector bucket contents and bucket
aws s3 rm s3://chatbot-vectors-${ACCOUNT_ID}-${REGION} --recursive
aws s3 rb s3://chatbot-vectors-${ACCOUNT_ID}-${REGION}

# Delete metadata bucket contents and bucket
aws s3 rm s3://chatbot-metadata-${ACCOUNT_ID}-${REGION} --recursive
aws s3 rb s3://chatbot-metadata-${ACCOUNT_ID}-${REGION}

# Delete website bucket contents and bucket (if exists)
aws s3 rm s3://chatbot-website-${ACCOUNT_ID}-${REGION} --recursive
aws s3 rb s3://chatbot-website-${ACCOUNT_ID}-${REGION}
```

### Step 3: Delete Bedrock Guardrails (If Created)

```bash
# List guardrails to find the one created by the chatbot
aws bedrock list-guardrails --region ${REGION}

# Delete the chatbot guardrail (replace GUARDRAIL_ID with actual ID)
aws bedrock delete-guardrail --guardrail-identifier GUARDRAIL_ID --region ${REGION}
```

### Step 4: Clean Up Lambda Functions (If Not Auto-Deleted)

```bash
# Delete Lambda functions
aws lambda delete-function --function-name ChatbotFunction --region ${REGION}
aws lambda delete-function --function-name DocumentProcessorFunction --region ${REGION}

# Delete Lambda layers (if any were created)
aws lambda list-layers --region ${REGION} | grep -i chatbot
# Delete any chatbot-related layers found
```

### Step 5: Delete API Gateway Resources (If Not Auto-Deleted)

```bash
# List REST APIs
aws apigateway get-rest-apis --region ${REGION} | grep -A 5 -B 5 "Chatbot"

# Delete REST API (replace API_ID with actual ID)
aws apigateway delete-rest-api --rest-api-id API_ID --region ${REGION}

# List WebSocket APIs
aws apigatewayv2 get-apis --region ${REGION} | grep -A 5 -B 5 "Chatbot"

# Delete WebSocket API (replace API_ID with actual ID)
aws apigatewayv2 delete-api --api-id API_ID --region ${REGION}
```

### Step 6: Clean Up IAM Roles and Policies (If Not Auto-Deleted)

```bash
# List IAM roles related to the chatbot
aws iam list-roles | grep -A 5 -B 5 "Chatbot"

# Delete IAM role (replace ROLE_NAME with actual name)
aws iam delete-role --role-name ROLE_NAME

# List and delete any custom policies
aws iam list-policies --scope Local | grep -A 5 -B 5 "Chatbot"
```

### Step 7: Delete CloudWatch Resources

```bash
# Delete log groups
aws logs delete-log-group --log-group-name /aws/lambda/ChatbotRagStack-Critical --region ${REGION}
aws logs delete-log-group --log-group-name /aws/lambda/ChatbotRagStack-Standard --region ${REGION}
aws logs delete-log-group --log-group-name /aws/lambda/ChatbotRagStack-Debug --region ${REGION}

# Delete CloudWatch dashboard
aws cloudwatch delete-dashboards --dashboard-names ChatbotMonitoring --region ${REGION}
```

### Step 8: Clean Up Local Files

```bash
# Remove deployment artifacts
rm -f .deployment_state.json
rm -f .rollback_state.json
rm -rf .deployment_checkpoints
rm -rf .deployment_backup
rm -f deployment.log

# Remove CDK output
rm -rf cdk.out

# Remove Python cache files
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete

# Remove virtual environment (if created)
rm -rf .venv
```

## 🔍 Verification Steps

After uninstalling, verify all resources are removed:

### 1. Check CloudFormation Stacks
```bash
aws cloudformation list-stacks --stack-status-filter DELETE_COMPLETE | grep ChatbotRagStack
```

### 2. Check S3 Buckets
```bash
aws s3 ls | grep chatbot
# Should return no results
```

### 3. Check Lambda Functions
```bash
aws lambda list-functions | grep -i chatbot
# Should return no results
```

### 4. Check API Gateway
```bash
aws apigateway get-rest-apis | grep -i chatbot
aws apigatewayv2 get-apis | grep -i chatbot
# Both should return no results
```

### 5. Check IAM Resources
```bash
aws iam list-roles | grep -i chatbot
aws iam list-policies --scope Local | grep -i chatbot
# Both should return no results
```

## 💰 Cost Verification

After uninstalling, verify no ongoing costs:

1. **Check AWS Billing Console**:
   - Go to AWS Billing & Cost Management
   - Review current month charges
   - Verify no charges for Lambda, API Gateway, S3, Bedrock

2. **Set up Billing Alerts** (if not already done):
   ```bash
   # Create a billing alarm for $1 to catch any unexpected charges
   aws cloudwatch put-metric-alarm \
     --alarm-name "ChatbotUnexpectedCharges" \
     --alarm-description "Alert for unexpected charges after chatbot uninstall" \
     --metric-name EstimatedCharges \
     --namespace AWS/Billing \
     --statistic Maximum \
     --period 86400 \
     --threshold 1.0 \
     --comparison-operator GreaterThanThreshold \
     --dimensions Name=Currency,Value=USD \
     --evaluation-periods 1
   ```

## 🆘 Troubleshooting Uninstall Issues

### Issue: CloudFormation Stack Deletion Fails

**Solution**:
```bash
# Check stack events for errors
aws cloudformation describe-stack-events --stack-name ChatbotRagStack

# Force delete stack (use with caution)
aws cloudformation delete-stack --stack-name ChatbotRagStack --retain-resources

# Then manually delete remaining resources
```

### Issue: S3 Buckets Won't Delete

**Solution**:
```bash
# Empty buckets first, then delete
aws s3 rm s3://BUCKET_NAME --recursive
aws s3api delete-bucket --bucket BUCKET_NAME
```

### Issue: Lambda Functions Still Exist

**Solution**:
```bash
# List all Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `Chatbot`)]'

# Delete each function
aws lambda delete-function --function-name FUNCTION_NAME
```

### Issue: API Gateway Resources Remain

**Solution**:
```bash
# Force delete API Gateway
aws apigateway delete-rest-api --rest-api-id API_ID
aws apigatewayv2 delete-api --api-id API_ID
```

## 📞 Support

If you encounter issues during uninstall:

1. **Check the troubleshooting section above**
2. **Review AWS CloudFormation events** for specific error messages
3. **Consult the main troubleshooting guide**: [docs/troubleshooting.md](troubleshooting.md)
4. **Manual cleanup**: Use the AWS Console to manually delete remaining resources

## ⚠️ Final Notes

- **Billing**: It may take up to 24 hours for AWS billing to reflect the resource deletions
- **Data Recovery**: Once deleted, data cannot be recovered. Ensure you have backups if needed
- **Regional Resources**: This guide assumes resources are in your default region. Adjust commands if deployed to a different region
- **Permissions**: Ensure your AWS credentials have sufficient permissions to delete all resources

**The uninstall process is complete when all verification steps return no results and no unexpected charges appear in your AWS billing.**
