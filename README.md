# RAG Chatbot - AI Assistant Example Project

> **⚠️ EXAMPLE PROJECT**: This demonstrates how to build a RAG chatbot using AWS services. Costs will vary based on usage. No warranty provided.

Deploy an AI chatbot that learns from your documents in ~15 minutes. **Starting at $23/month**.

## 🚀 Quick Start

```bash
# One-command deployment
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/chatbot-rag-v1.0/main/install.sh | bash

# Or manual deployment
git clone https://github.com/YOUR_USERNAME/chatbot-rag-v1.0.git
cd chatbot-rag-v1.0
./deploy.sh deploy
```

**⚠️ Replace `YOUR_USERNAME` with your GitHub username**

## ✨ Features

- **Amazon Nova Lite** for fast AI responses
- **S3 Vectors** for scalable document embeddings storage
- **Real-time streaming** via WebSocket
- **Content moderation** with Bedrock Guardrails
- **Multi-format documents** (PDF, TXT, images with OCR)
- **Enterprise security** (WAF, rate limiting, PII detection)
- **Auto-scaling** serverless architecture

## 📋 Prerequisites

- AWS Account with billing enabled
- AWS CLI configured (`aws configure`)
- Python 3.9+ installed
- Git installed

## 🛠️ Commands

```bash
./deploy.sh deploy     # Deploy chatbot
./deploy.sh status     # Check status
./deploy.sh rollback   # Remove deployment
./deploy.sh cleanup-s3 # Empty S3 buckets only
```

## 📚 Document Management

```bash
# Process documents locally (recommended)
python3 scripts/process_documents_locally.py --folder ./documents

# Process single document
python3 scripts/process_documents_locally.py --file ./doc.pdf

# Delete document
python3 scripts/process_documents_locally.py --delete "document-id"
```

## 💰 Estimated Costs

| Users/Day | Monthly Cost |
|-----------|--------------|
| 50        | $23          |
| 250       | $60          |
| 500       | $115         |

*Includes AI processing, hosting, vector storage, security*

## 🏗️ Architecture

- **Frontend**: JavaScript widget with WebSocket support
- **Backend**: Python Lambda functions (Graviton3)
- **AI**: Amazon Nova Lite + Titan Embeddings
- **Storage**: S3 Vector buckets for embeddings
- **Security**: WAF, Guardrails, rate limiting
- **CDN**: CloudFront for global delivery

## 🧪 Testing

```bash
# Run tests
python3 run_tests.py

# Test with coverage
python3 run_tests.py --coverage

# Validate configuration
python3 src/backend/config_validator.py
```

## 📖 Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide
- **[docs/troubleshooting.md](docs/troubleshooting.md)** - Common issues
- **[docs/api-spec.yaml](docs/api-spec.yaml)** - API documentation

## 🆘 Need Help?

1. Check deployment logs: `deployment.log`
2. Run: `./deploy.sh status`
3. See troubleshooting guide: `docs/troubleshooting.md`

## 📄 License

MIT License - Free for commercial and personal use.

---

**Ready to deploy?**
```bash
./deploy.sh deploy
```
