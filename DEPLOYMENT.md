# 🚀 RAG Chatbot - Complete Deployment Guide

> **⚠️ DISCLAIMER**: This project is an example of how you can design and deploy a small scale chatbot leveraging AWS services such as AWS Lambda, Amazon Bedrock, and AWS API Gateway. The focus in this example is on keeping costs as low as possible while also upholding strong security principles and protections. By deploying this project you will incur costs that will depend on your actual utilization. No support or warranty is provided. This example is not endorsed or supported by AWS.

This is the **complete and authoritative deployment guide** for the RAG Chatbot solution. All other deployment documentation references this guide.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Recommended)](#quick-start-recommended)
3. [Atomic Deployment (Production)](#atomic-deployment-production)
4. [Manual Deployment](#manual-deployment)
5. [Configuration](#configuration)
6. [Post-Deployment Setup](#post-deployment-setup)
7. [Document Management](#document-management)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Uninstalling](#uninstalling)
10. [Troubleshooting](#troubleshooting)
11. [Cost Management](#cost-management)
12. [Security Considerations](#security-considerations)

## 📋 Prerequisites

### Required
- ✅ **AWS Account** with billing enabled
- ✅ **AWS CLI** installed and configured (`aws configure`)
- ✅ **Python 3.12+** installed (3.9+ minimum)
- ✅ **Git** installed
- ✅ **Internet connection** for downloading dependencies

### Optional (for enhanced features)
- ✅ **jq** installed (for atomic deployment with rollback)
- ✅ **scikit-learn** (auto-installed for vector clustering optimization)

### AWS Permissions Required
Your AWS user/role needs the following permissions:
- `AdministratorAccess` (recommended for initial deployment)
- Or specific permissions for: Lambda, API Gateway, S3, Bedrock, CloudFormation, IAM, CloudWatch, WAF

## 🚀 Quick Start (Recommended)

### One-Command Deployment

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/chatbot-rag-v1.0/main/install.sh | bash
```

**⚠️ IMPORTANT**: Replace `YOUR_USERNAME` with your actual GitHub username.

This script will:
1. ✅ Clone the repository
2. ✅ Install all dependencies automatically
3. ✅ Configure AWS CDK
4. ✅ Deploy the complete infrastructure
5. ✅ Set up monitoring and security
6. ✅ Provide integration code

**Expected time**: 15-20 minutes

## ⚡ Deployment (Production Ready)

The deployment uses atomic deployment with automatic rollback capabilities:

```bash
git clone https://github.com/davidgendel/aws-bedrock-chatbot-solution.git
cd aws-bedrock-chatbot-solution
./deploy.sh deploy
```

### Deployment Features:
- **🔄 Automatic Rollback**: If any phase fails, automatically rolls back changes
- **📊 State Management**: Tracks deployment progress with checkpoints
- **🛡️ Resource Cleanup**: Cleans up failed resources automatically
- **📈 Progress Tracking**: Real-time deployment status
- **🔍 Error Analysis**: Detailed error reporting and recovery suggestions

### Deployment Commands:
```bash
# Deploy with atomic guarantees
./deploy.sh deploy

# Check deployment status
./deploy.sh status

# Manual rollback if needed
./deploy.sh rollback

# Get help
./deploy.sh help
```

## 🛠️ Manual Deployment

### Step 1: Clone and Setup
```bash
git clone https://github.com/davidgendel/aws-bedrock-chatbot-solution.git
cd aws-bedrock-chatbot-solution
```

### Step 2: Install Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install -r requirements-dev.txt

# Install Node.js dependencies
npm install -g aws-cdk
```

### Step 3: Configure AWS
```bash
# Configure AWS credentials
aws configure

# Bootstrap CDK (if not done before)
cdk bootstrap
```

### Step 4: Deploy Infrastructure
```bash
# Standard deployment
./deploy.sh

# Or with recovery options
./deploy.sh --recover  # Resume from last checkpoint
./deploy.sh --clean    # Clean up and start fresh
```

## ⚙️ Configuration

### Environment Variables
The system uses these key environment variables:

```bash
# Core Configuration
VECTOR_BUCKET_NAME=your-vector-bucket
VECTOR_INDEX_NAME=chatbot-index
DOCUMENT_BUCKET_NAME=your-document-bucket

# Performance Settings
USE_ASYNC_PROCESSING=true
MAX_BATCH_SIZE=10
VECTOR_CACHE_SIZE=1000

# Security Settings
ENABLE_CONTENT_FILTERING=true
RATE_LIMIT_PER_MINUTE=60
```

### Configuration File (config.json)
```json
{
  "deployment": {
    "region": "us-east-1",
    "environment": "production",
    "atomic_deployment": true
  },
  "vector_storage": {
    "provider": "s3_vectors",
    "index_type": "hnsw",
    "dimensions": 1536,
    "similarity_metric": "cosine"
  },
  "performance": {
    "enable_caching": true,
    "batch_processing": true,
    "async_processing": true
  },
  "security": {
    "enable_waf": true,
    "content_filtering": true,
    "pii_detection": true
  }
}
```

## 🎯 Post-Deployment Setup

### 1. Verify Deployment
```bash
# Check deployment status
./deploy.sh status

# Test API endpoints
curl -X GET https://your-api-endpoint/health

# Check CloudFormation stack
aws cloudformation describe-stacks --stack-name ChatbotRagStack
```

### 2. Test Your Chatbot (Sample Demo Page)

**📄 Use the included sample page to test your deployment:**

**Location**: `src/frontend/index.html`

```bash
# Open the sample page in your browser
open src/frontend/index.html
# or on Linux
firefox src/frontend/index.html
# or
chrome src/frontend/index.html
```

**✨ The demo page includes:**
- **Interactive chatbot widget** with your deployed configuration
- **Test controls** for caching, streaming, and WebSocket features
- **Example questions** to get started
- **Connection status** indicator
- **Performance testing** tools (cache clearing, reconnection)

**💡 Pro tip**: Use this sample page to validate your deployment and test new features before integrating into your website.

### 3. Upload Initial Documents
```bash
# Upload documents from a folder
python3 -m scripts.upload_documents --folder ./documents

# Upload single document
python3 -m scripts.upload_documents --file document.pdf
```

### 4. Optimize Vector Index
```bash
# Optimize for better search performance
python3 scripts/manage_vector_indexes.py --optimize

# Check optimization status
python3 scripts/manage_vector_indexes.py --status
```

### 5. Integration Testing
1. Open the provided sample HTML file (`src/frontend/index.html`)
2. Test with sample questions
3. Verify document retrieval works
4. Check response streaming

## 📚 Document Management

### Supported Formats
- **Text**: PDF, Word (DOCX), TXT, Markdown
- **Web**: HTML, CSV, JSON
- **Images**: PNG, JPG, JPEG, TIFF (with OCR)

### Upload Methods

#### Batch Upload
```bash
# Upload entire folder
python3 -m scripts.upload_documents --folder ./documents --batch-size 5

# Upload with specific file types
python3 -m scripts.upload_documents --folder ./docs --types pdf,docx,txt
```

#### Programmatic Upload
```python
from scripts.upload_documents import upload_document

# Upload single document
result = upload_document("path/to/document.pdf")
print(f"Uploaded: {result['document_id']}")
```

### Document Processing Status
```bash
# Check processing status
python3 -c "
from src.backend.document_processor import handler
result = handler({'action': 'status'}, None)
print(result)
"
```

## 📊 Monitoring & Maintenance

### Performance Monitoring
```bash
# Check vector index performance
python3 scripts/manage_vector_indexes.py --stats

# Monitor API performance
aws logs tail /aws/lambda/ChatbotRagStack-ChatbotFunction --follow

# Check cost metrics
aws ce get-cost-and-usage --time-period Start=2025-01-01,End=2025-12-31 --granularity MONTHLY --metrics BlendedCost
```

### Regular Maintenance
```bash
# Clean up old vectors (90+ days)
python3 scripts/cleanup_vectors.py --days 90

# Optimize vector indexes monthly
python3 scripts/manage_vector_indexes.py --optimize

# Update dependencies
pip install -r requirements.txt --upgrade
```

### Health Checks
```bash
# System health check
./deploy.sh status

# API health check
curl https://your-api-endpoint/health

# Vector index health
python3 scripts/manage_vector_indexes.py --health-check
```

## 🗑️ Uninstalling

To completely remove the chatbot and all AWS resources:

### Quick Uninstall (Recommended)
```bash
# Automatic rollback/uninstall
./deploy.sh rollback
```

This will:
- ✅ Delete the CloudFormation stack and all AWS resources
- ✅ Clean up local deployment artifacts  
- ✅ Remove temporary files and state

### Manual Uninstall
If automatic rollback fails, follow the manual steps in our comprehensive guide:

**📋 [Complete Uninstall Guide](docs/uninstall-guide.md)**

The manual process includes:
- CloudFormation stack deletion
- S3 bucket cleanup
- Lambda function removal
- API Gateway cleanup
- IAM role deletion
- Local file cleanup

**⚠️ Warning**: Uninstalling permanently deletes all data and cannot be undone.

## 🆘 Troubleshooting

### Common Issues

#### Deployment Failed
```bash
# Check deployment logs
cat deployment.log

# Try recovery
./deploy.sh --recover

# Or rollback and retry
./deploy.sh rollback
./deploy.sh deploy
```

#### Chatbot Not Responding
1. **Check API Gateway**: Verify endpoints are active
2. **Check Lambda**: Look for errors in CloudWatch logs
3. **Check Vector Index**: Ensure documents are processed
4. **Check Permissions**: Verify IAM roles are correct

#### Performance Issues
```bash
# Optimize vector index
python3 scripts/manage_vector_indexes.py --optimize

# Check cache performance
python3 -c "
from src.backend.cache_manager import get_cache_stats
print(get_cache_stats())
"

# Monitor resource usage
aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Duration --dimensions Name=FunctionName,Value=ChatbotFunction --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z --period 3600 --statistics Average
```

### Error Recovery
```bash
# Automatic error analysis
python3 scripts/error_analyzer.py deployment.log

# Recovery manager
python3 scripts/recovery_manager.py --analyze --fix

# Manual cleanup
python3 scripts/cleanup_database.py --force
```

## 💰 Cost Management

### Cost Optimization
- **Vector Storage**: Use S3 Vectors for cost-effective scaling
- **Lambda**: Graviton3 processors for 20% cost savings
- **Caching**: Reduces API calls and improves performance
- **Rate Limiting**: Prevents unexpected usage spikes

### Cost Monitoring
```bash
# Daily cost check
aws ce get-cost-and-usage --time-period Start=$(date -d '1 day ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) --granularity DAILY --metrics BlendedCost

# Set up cost alerts
aws budgets create-budget --account-id YOUR_ACCOUNT_ID --budget file://budget.json
```

### Expected Costs (Monthly)
| Component | Small (50 users) | Medium (500 users) | Large (5000 users) |
|-----------|------------------|--------------------|--------------------|
| Lambda | $5.00 | $25.00 | $150.00 |
| S3 Vectors | $8.00 | $35.00 | $200.00 |
| API Gateway | $3.00 | $15.00 | $80.00 |
| CloudFront | $2.00 | $8.00 | $40.00 |
| Bedrock | $10.00 | $45.00 | $250.00 |
| **Total** | **$28.00** | **$128.00** | **$720.00** |

## 🔒 Security Considerations

### Security Features
- **AWS WAF**: DDoS protection and bot filtering
- **Content Filtering**: Bedrock Guardrails for safe responses
- **PII Detection**: Automatic detection and blocking
- **Rate Limiting**: Prevents abuse and controls costs
- **Encryption**: All data encrypted in transit and at rest

### Security Best Practices
1. **Regular Updates**: Keep dependencies updated
2. **Access Control**: Use least-privilege IAM policies
3. **Monitoring**: Enable CloudTrail and GuardDuty
4. **Backup**: Regular backups of configuration and data
5. **Testing**: Regular security testing and penetration testing

### Compliance
- **GDPR**: PII detection and data handling
- **SOC 2**: AWS infrastructure compliance
- **ISO 27001**: AWS certified infrastructure

---

## 🎉 Deployment Complete!

After successful deployment, you'll have:
- ✅ Production-ready AI chatbot
- ✅ Scalable vector storage with S3 Vectors
- ✅ Monitoring and alerting
- ✅ Security and compliance features
- ✅ Integration code for your website

**Next Steps:**
1. Upload your documents
2. Test the chatbot thoroughly
3. Integrate into your website
4. Monitor performance and costs
5. Scale as needed

**Need Help?** Check our [Troubleshooting Guide](docs/troubleshooting.md) or [FAQ](docs/faq.md).
1. ✅ Clone the repository
2. ✅ Install all dependencies automatically
3. ✅ Validate your AWS configuration
4. ✅ Check system requirements
5. ✅ Deploy the complete infrastructure
6. ✅ Set up the knowledge base
7. ✅ Provide you with the integration code

**Estimated time**: 10-15 minutes

### What Happens During Deployment

The deployment script performs these steps:

1. **Environment Setup** (2-3 minutes)
   - Installs Python dependencies
   - Installs Node.js and AWS CDK
   - Validates AWS credentials

2. **Configuration Validation** (30 seconds)
   - Validates `config.json` settings
   - Checks for required parameters
   - Warns about potential issues

3. **Infrastructure Deployment** (5-8 minutes)
   - Creates AWS resources using CDK
   - Sets up Lambda functions
   - Configures API Gateway and WebSocket API
   - Creates S3 buckets and vector indexes
   - Sets up CloudFront distribution
   - Configures WAF protection

4. **Knowledge Base Setup** (1-2 minutes)
   - Creates vector indexes
   - Processes any existing documents
   - Sets up document processing pipeline

5. **Finalization** (30 seconds)
   - Generates integration code
   - Creates monitoring dashboards
   - Provides deployment summary

## 🔧 Manual Deployment

If you prefer manual control or the quick start fails:

### Step 1: Clone Repository

```bash
git clone https://github.com/davidgendel/aws-bedrock-chatbot-solution.git
cd aws-bedrock-chatbot-solution
```

### Step 2: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements-dev.txt

# Install Node.js (if not already installed)
# Ubuntu/Debian:
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# macOS:
brew install node

# Install AWS CDK
npm install -g aws-cdk
```

### Step 3: Configure AWS

```bash
# Configure AWS CLI (if not already done)
aws configure

# Verify configuration
aws sts get-caller-identity
```

### Step 4: Validate Configuration

```bash
# Validate configuration file
python3 src/backend/config_validator.py config.json
```

### Step 5: Deploy Infrastructure

```bash
# Run deployment script
./deploy.sh
```

### Step 6: Verify Deployment

```bash
# Check deployment status
aws cloudformation describe-stacks --stack-name ChatbotRagStack

# Test the API
curl -X POST https://your-api-id.execute-api.region.amazonaws.com/prod/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"message": "Hello, how can you help me?"}'
```

## ⚙️ Configuration

### Basic Configuration (`config.json`)

```json
{
  "region": "us-east-1",
  "lambda": {
    "chatbot": {
      "provisionedConcurrency": {
        "enabled": true,
        "concurrentExecutions": 1
      }
    }
  },
  "api": {
    "throttling": {
      "ratePerMinute": 10,
      "ratePerHour": 100
    }
  },
  "widget": {
    "defaultTheme": {
      "primaryColor": "#4287f5",
      "secondaryColor": "#f5f5f5",
      "fontFamily": "Arial, sans-serif",
      "fontSize": "16px",
      "borderRadius": "8px"
    }
  },
  "bedrock": {
    "modelId": "amazon.nova-lite-v1",
    "guardrails": {
      "createDefault": true
    }
  }
}
```

### Configuration Validation

Always validate your configuration before deployment:

```bash
python3 src/backend/config_validator.py config.json
```

### Environment Variables

The deployment automatically sets these environment variables:

- `AWS_REGION`: Your selected AWS region
- `VECTOR_INDEX_NAME`: Name of the S3 vector index
- `GUARDRAIL_ID`: Bedrock guardrail identifier
- `API_KEY`: Generated API key for authentication

## 🔄 Post-Deployment Setup

### 1. Get Your Integration Code

After deployment, you'll receive HTML code like this:

```html
<!-- Add this to your website's <head> section -->
<script src="https://your-cloudfront-id.cloudfront.net/widget.js"></script>

<!-- Add this where you want the chatbot to appear -->
<div id="chatbot-container"></div>

<script>
SmallBizChatbot.init({
  containerId: 'chatbot-container',
  apiEndpoint: 'https://your-api-id.execute-api.region.amazonaws.com/prod',
  apiKey: 'your-api-key',
  websocketUrl: 'wss://your-websocket-id.execute-api.region.amazonaws.com/prod',
  theme: {
    primaryColor: '#4287f5',
    secondaryColor: '#f5f5f5'
  }
});
</script>
```

### 2. Test Your Chatbot

1. **Basic Test**: Visit your website and try asking a question
2. **API Test**: Use curl or Postman to test the API directly
3. **WebSocket Test**: Test streaming responses if enabled

### 3. Upload Your Documents

```bash
# Upload documents to create your knowledge base
python3 -m scripts.upload_documents --folder ./your-documents-folder
```

Supported formats:
- PDF files (`.pdf`)
- Word documents (`.docx`)
- Text files (`.txt`)
- Markdown files (`.md`)

## 📚 Document Management

### Adding Documents

```bash
# Upload new documents
python3 -m scripts.upload_documents --folder ./documents

# Upload specific file types
python3 -m scripts.upload_documents --folder ./documents --types pdf,docx

# Upload with custom metadata
python3 -m scripts.upload_documents --folder ./documents --metadata '{"category": "support"}'
```

### Managing Vector Indexes

```bash
# View vector index status
python3 scripts/manage_vector_indexes.py --status

# Rebuild vector index
python3 scripts/manage_vector_indexes.py --rebuild

# Clean up old vectors
python3 scripts/cleanup_vectors.py --days 90
```

### Document Processing Pipeline

1. **Upload**: Documents uploaded to S3 trigger processing
2. **Text Extraction**: Content extracted using Amazon Textract
3. **Chunking**: Documents split into semantic chunks
4. **Embedding**: Chunks converted to vectors using Amazon Titan
5. **Indexing**: Vectors stored in S3 Vector indexes
6. **Availability**: New content immediately available for queries

## 📊 Monitoring & Maintenance

### CloudWatch Dashboards

Access your monitoring dashboards:
1. Go to AWS CloudWatch Console
2. Navigate to Dashboards
3. Find "ChatbotRag-Dashboard"

Key metrics to monitor:
- **API Request Volume**: Track usage patterns
- **Response Times**: Monitor performance
- **Error Rates**: Identify issues
- **Cost Metrics**: Track spending

### Regular Maintenance Tasks

#### Weekly
- Review CloudWatch logs for errors
- Check API usage and costs
- Update documents if needed

#### Monthly
- Clean up old vector data
- Review and update guardrails
- Analyze usage patterns
- Update dependencies

#### Quarterly
- Review security settings
- Update AWS service configurations
- Optimize costs based on usage
- Update documentation

### Maintenance Commands

```bash
# Check system health
python3 scripts/deployment_validator.py --health-check

# Clean up old data
python3 scripts/cleanup_vectors.py --days 30

# Update dependencies
pip install -r requirements-dev.txt --upgrade

# Redeploy with updates
./deploy.sh --update
```

## 🔍 Troubleshooting

### Common Issues

#### Deployment Fails

```bash
# Check deployment logs
cat deployment.log

# Recover from failed deployment
./deploy.sh --recover

# Clean up and start fresh
./deploy.sh --rollback
```

#### Chatbot Not Responding

1. **Check API Key**: Ensure correct API key in integration code
2. **Check CORS**: Verify your domain is allowed
3. **Check Logs**: Review CloudWatch logs for errors
4. **Test API**: Use curl to test API directly

```bash
# Test API endpoint
curl -X POST https://your-api-id.execute-api.region.amazonaws.com/prod/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"message": "test"}'
```

#### High Costs

1. **Check Usage**: Review CloudWatch metrics
2. **Adjust Limits**: Reduce rate limits in config
3. **Optimize Concurrency**: Reduce provisioned concurrency
4. **Review Documents**: Remove unnecessary documents

#### Performance Issues

1. **Check Provisioned Concurrency**: Increase if needed
2. **Review Vector Index**: Optimize index configuration
3. **Check Document Size**: Large documents slow processing
4. **Monitor Memory**: Increase Lambda memory if needed

### Getting Help

1. **Check Logs**: Always start with CloudWatch logs
2. **Review Documentation**: Check this guide and AWS docs
3. **Validate Configuration**: Run config validator
4. **Test Components**: Test individual components

### Error Recovery

```bash
# Automatic error analysis
python3 scripts/error_analyzer.py deployment.log

# Recovery options
./deploy.sh --recover    # Resume from last point
./deploy.sh --rollback   # Rollback and start fresh
./deploy.sh --clean      # Clean up resources
```

## 💰 Cost Management

### Cost Breakdown

**Small Business (50 users/day)**:
- Total: **$29.76/month**
- Security (WAF): $8.01/month (53.7%)
- S3 Vector Storage: $2.50/month (16.8%)
- AI/ML (Bedrock): $0.94/month (6.3%)
- Compute (Lambda): $1.11/month (7.4%)

**Growing Business (150 users/day)**:
- Total: **$33.52/month**
- Security (WAF): $8.03/month (42.1%)
- S3 Vector Storage: $3.75/month (19.7%)
- AI/ML (Bedrock): $3.35/month (17.6%)

### Cost Optimization

#### Immediate Actions
1. **Adjust Rate Limits**: Reduce in `config.json`
2. **Optimize Concurrency**: Reduce provisioned concurrency
3. **Clean Up Data**: Remove old vectors and documents
4. **Monitor Usage**: Set up billing alerts

#### Configuration Changes
```json
{
  "api": {
    "throttling": {
      "ratePerMinute": 5,    // Reduced from 10
      "ratePerHour": 50      // Reduced from 100
    }
  },
  "lambda": {
    "chatbot": {
      "provisionedConcurrency": {
        "enabled": false     // Disable to save costs
      }
    }
  }
}
```

#### Monitoring Commands
```bash
# Check current costs
aws ce get-cost-and-usage --time-period Start=2024-01-01,End=2024-01-31 --granularity MONTHLY --metrics BlendedCost

# Set up billing alerts
aws budgets create-budget --account-id YOUR_ACCOUNT_ID --budget file://budget.json
```

### Billing Alerts

Set up automatic billing alerts:

1. Go to AWS Billing Console
2. Create Budget
3. Set threshold (e.g., $50/month)
4. Configure email notifications

## 🔒 Security Considerations

### Built-in Security Features

- **AWS WAF**: Protects against common attacks
- **API Key Authentication**: Secures API access
- **Rate Limiting**: Prevents abuse
- **Content Moderation**: Bedrock guardrails filter content
- **Encryption**: All data encrypted at rest and in transit
- **IAM Roles**: Least privilege access

### Security Best Practices

#### API Security
- Rotate API keys regularly
- Use HTTPS only
- Implement proper CORS policies
- Monitor for unusual usage patterns

#### Data Security
- Regularly review document access
- Clean up old data
- Monitor for sensitive data exposure
- Use strong guardrail configurations

#### Infrastructure Security
- Keep dependencies updated
- Review IAM permissions regularly
- Enable CloudTrail logging
- Monitor security events

### Security Commands

```bash
# Rotate API keys
aws apigateway create-api-key --name "ChatbotKey-$(date +%Y%m%d)"

# Review security logs
aws logs filter-log-events --log-group-name /aws/lambda/chatbot --filter-pattern "ERROR"

# Update guardrails
python3 scripts/update_guardrails.py --config security-config.json
```

## 🎯 Next Steps

After successful deployment:

1. **Customize Appearance**: Modify widget theme in `config.json`
2. **Add Documents**: Upload your business documents
3. **Test Thoroughly**: Test with real user scenarios
4. **Monitor Performance**: Set up alerts and monitoring
5. **Optimize Costs**: Adjust settings based on usage
6. **Scale Up**: Increase limits as usage grows


---

**🎉 Congratulations!** You now have a production-ready AI chatbot that learns from your documents. The solution is designed to be cost-effective, secure, and easy to maintain.

**Remember**: This is a complete example solution. Customize it to fit your specific business needs and requirements.
