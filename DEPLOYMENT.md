# 🚀 RAG Chatbot - Deployment Guide

> **⚠️ DISCLAIMER**: This project is an example of how you can design and deploy a small scale chatbot leveraging AWS services. By deploying this project you will incur costs that will depend on your actual utilization. No support or warranty is provided.

## 📋 Prerequisites

### Required
- ✅ **AWS Account** with proper permissions
- ✅ **AWS CLI 2.27+** installed and configured (`aws configure`)
- ✅ **Python 3.12+** installed
- ✅ **Python venv** installed
- ✅ **Node 22+** installed (for aws cdk)
- ✅ **Git** installed
- ✅ **Docker** installed (for Lambda layers)

### AWS Permissions Required
Your AWS user/role needs:
- `AdministratorAccess` (recommended for initial deployment)
- Or specific permissions for: Lambda, API Gateway, S3, S3 Vectors, Bedrock, CloudFormation, IAM, CloudWatch, WAF

## 🚀 Quick Start

### For Beginners

**What You'll Need:**
1. **A computer** (Windows, Mac, or Linux)
2. **An AWS account** (see AWS Account Setup below)
3. **About 15 minutes** of your time

**How to Open Terminal/Command Prompt:**
- **Windows**: Press `Win + R`, type `cmd`, press Enter
- **Mac**: Press `Cmd + Space`, type "Terminal", press Enter
- **Linux**: Press `Ctrl + Alt + T`

### Deployment

```bash
git clone https://github.com/your-github-username/aws-bedrock-chatbot-solution.git
cd aws-bedrock-chatbot-solution

# Optional: Validate your environment first
./chatbot validate

# Deploy the chatbot
./chatbot deploy
```

**⚠️ IMPORTANT**: Replace `your-github-username` with your actual GitHub username.

**Expected time**: 15-20 minutes

### AWS Account Setup (For Beginners)

If you don't have an AWS account:

1. **Create an AWS Account**:
   - Go to [aws.amazon.com](https://aws.amazon.com)
   - Click "Create an AWS Account"
   - Follow the signup process (you'll need a credit card)

2. **Install AWS CLI**:
   
   **Windows:**
   ```cmd
   # Download and install from: https://aws.amazon.com/cli/
   # After installation, open Command Prompt and run:
   aws configure
   ```
   
   **Mac:**
   ```bash
   # Install using Homebrew (get it from brew.sh if needed)
   brew install awscli
   aws configure
   ```
   
   **Linux:**
   ```bash
   sudo apt install awscli  # Ubuntu/Debian
   # or
   sudo yum install awscli  # CentOS/RHEL
   aws configure
   ```

3. **Configure AWS CLI**:
   When you run `aws configure`, enter:
   - **Access Key ID**: Get from AWS Console → IAM → Users → Your User → Security Credentials
   - **Secret Access Key**: You'll get this with the Access Key
   - **Region**: Choose closest to you (e.g., `us-east-1` for US East Coast)
   - **Output format**: Just press Enter

### Deployment Commands:
```bash
# Validate environment before deployment (recommended)
./chatbot validate

# Deploy with atomic guarantees
./chatbot deploy

# Check deployment status
./chatbot status

# Manual rollback if needed
./chatbot rollback

# Empty S3 buckets only
./chatbot cleanup --s3-only
```

## 📚 Post-Deployment Setup

### 1. Add Documents
```bash
# Create documents folder and add your files
mkdir -p documents
cp your-files.pdf ./documents/

# Process documents (dependencies handled automatically)
./process_documents --folder ./documents
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
./chatbot cleanup --s3-only
```

**Lambda timeout**: Check CloudWatch logs
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ChatbotRag"
```

### Getting Help
1. Check `deployment.log` for detailed error messages
2. Run `./chatbot status` to see current state
3. See `docs/troubleshooting.md` for detailed solutions

## 💰 Cost Management

For detailed cost information and estimates, see the [Cost Analysis Guide](docs/cost-analysis.md).

## 🗑️ Uninstalling

```bash
# Complete removal
./chatbot rollback

# Manual cleanup if needed
./chatbot cleanup --s3-only
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
./chatbot deploy
```
