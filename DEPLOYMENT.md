# 🚀 RAG Chatbot - Deployment Guide

> **⚠️ DISCLAIMER**: This project is an example of how you can design and deploy a small scale chatbot leveraging AWS services. By deploying this project you will incur costs that will depend on your actual utilization. No support or warranty is provided.

## 📋 Prerequisites

### Required
- ✅ **AWS Account** with billing enabled
- ✅ **AWS CLI 2.27+ ** installed and configured (`aws configure`)
- ✅ **Python 3.12+** installed
- ✅ **Git** installed

### AWS Permissions Required
Your AWS user/role needs:
- `AdministratorAccess` (recommended for initial deployment)
- Or specific permissions for: Lambda, API Gateway, S3, S3 Vectors, Bedrock, CloudFormation, IAM, CloudWatch, WAF

## 🚀 Quick Start

### One-Command Deployment

```bash
curl -sSL https://raw.githubusercontent.com/your-github-username/aws-bedrock-chatbot-solution/main/install.sh | bash
```

**⚠️ IMPORTANT**: Replace `your-github-username` with your actual GitHub username.

**Expected time**: 15-20 minutes

## ⚡ Manual Deployment

```bash
git clone https://github.com/your-github-username/aws-bedrock-chatbot-solution.git
cd aws-bedrock-chatbot-solution
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
# Create documents folder and add your files
mkdir -p documents
cp your-files.pdf ./documents/

# Install document processing dependencies
pip install -r scripts/requirements.txt

# Process documents
python3 scripts/process_documents_locally.py --folder ./documents
```

### 2. Get Integration Code
After deployment, check the deployment output for HTML/JavaScript code to embed the chatbot on your website.

### 3. Test the Chatbot
Use the API Gateway URL provided in the deployment output to test the chatbot.

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
- **50 users/day**: $11
- **250 users/day**: $40
- **500 users/day**: $79

*Includes AI processing, hosting, vector storage, security, and 20% caching savings*

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
