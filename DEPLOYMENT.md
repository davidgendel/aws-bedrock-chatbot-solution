# 🚀 RAG Chatbot - Deployment Guide

> **⚠️ DISCLAIMER**: This project is an example of how you can design and deploy a small scale chatbot leveraging AWS services. By deploying this project you will incur costs that will depend on your actual utilization. No support or warranty is provided.

## 📋 Prerequisites

### Required
- ✅ **AWS Account** with billing enabled
- ✅ **AWS CLI** installed and configured (`aws configure`)
- ✅ **Python 3.9+** installed
- ✅ **Git** installed

### AWS Permissions Required
Your AWS user/role needs:
- `AdministratorAccess` (recommended for initial deployment)
- Or specific permissions for: Lambda, API Gateway, S3, S3 Vectors, Bedrock, CloudFormation, IAM, CloudWatch, WAF

## 🚀 Quick Start

### One-Command Deployment

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/chatbot-rag-v1.0/main/install.sh | bash
```

**⚠️ IMPORTANT**: Replace `YOUR_USERNAME` with your actual GitHub username.

**Expected time**: 15-20 minutes

## ⚡ Manual Deployment

```bash
git clone https://github.com/YOUR_USERNAME/chatbot-rag-v1.0.git
cd chatbot-rag-v1.0
./deploy.sh deploy
```

### Deployment Commands:
```bash
# Deploy with atomic guarantees
./deploy.sh deploy

# Check deployment status
./deploy.sh status

# Manual rollback if needed
./deploy.sh rollback

# Empty S3 buckets only
./deploy.sh cleanup-s3
```

## 📚 Post-Deployment Setup

### 1. Add Documents
```bash
# Copy your documents to the documents folder
cp your-files.pdf ./documents/

# Process documents
python3 scripts/process_documents_locally.py --folder ./documents
```

### 2. Get Integration Code
After deployment, you'll receive HTML/JavaScript code to embed the chatbot on your website.

### 3. Test the Chatbot
The deployment will provide a test URL to verify everything works.

## 🔧 Configuration

Edit `config.json` to customize:
- **Region**: AWS region for deployment
- **API throttling**: Rate limits
- **Widget theme**: Colors and styling
- **Vector settings**: Embedding dimensions and similarity metric
- **Bedrock settings**: AI model and guardrails

## 🛠️ Troubleshooting

### Common Issues

**Deployment fails**: Check AWS credentials and permissions
```bash
aws sts get-caller-identity
```

**S3 bucket errors**: Empty buckets before rollback
```bash
./deploy.sh cleanup-s3
```

**Lambda timeout**: Check CloudWatch logs
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ChatbotRag"
```

### Getting Help
1. Check `deployment.log` for detailed error messages
2. Run `./deploy.sh status` to see current state
3. See `docs/troubleshooting.md` for detailed solutions

## 💰 Cost Management

### Estimated Monthly Costs
- **50 users/day**: ~$23
- **250 users/day**: ~$60
- **500 users/day**: ~$115

### Cost Optimization
- Monitor usage in CloudWatch
- Adjust Lambda concurrency settings
- Review API Gateway throttling limits
- Clean up old document vectors periodically

## 🗑️ Uninstalling

```bash
# Complete removal
./deploy.sh rollback

# Manual cleanup if needed
./deploy.sh cleanup-s3
aws cloudformation delete-stack --stack-name ChatbotRagStack
```

## 🔒 Security Considerations

- API keys are managed by AWS API Gateway
- All data encrypted in transit and at rest
- WAF protection enabled by default
- Content filtering via Bedrock Guardrails
- No sensitive data stored in logs

---

**Ready to deploy?**
```bash
./deploy.sh deploy
```
