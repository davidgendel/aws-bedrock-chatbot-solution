# RAG Chatbot - AI Assistant Example Project

> **⚠️ EXAMPLE PROJECT**: This demonstrates how to build a RAG chatbot using AWS services. Costs will vary based on usage. No warranty provided.

Deploy an AI chatbot that learns from your documents in ~15 minutes. **Starting at $11/month**.

## 🚀 Quick Start

```bash
# One-command deployment
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/aws-bedrock-chatbot-solution/main/install.sh | bash

# Or manual deployment
git clone https://github.com/YOUR_USERNAME/aws-bedrock-chatbot-solution.git
cd aws-bedrock-chatbot-solution
./deploy.sh deploy
```

**⚠️ Replace `YOUR_USERNAME` with your GitHub username**

## ✨ Features

- **Amazon Nova Lite** for fast AI responses
- **S3 Vectors** for scalable document embeddings storage
- **One-command vector optimization** with built-in performance monitoring
- **Real-time streaming** via WebSocket
- **Content moderation** with Bedrock Guardrails
- **Multi-format documents** (PDF, TXT, images with OCR)
- **Enterprise security** (WAF, rate limiting, PII detection)
- **Auto-scaling** serverless architecture
- **Multi-layer caching** for 20% cost savings

## 📋 Prerequisites

- AWS Account with billing enabled
- AWS CLI configured (`aws configure`)
- Python 3.9+ installed
- Git installed

## 🛠️ Commands

```bash
./deploy.sh deploy     # Deploy chatbot (no pip install needed)
./deploy.sh status     # Check status
./deploy.sh rollback   # Remove deployment
./deploy.sh cleanup-s3 # Empty S3 buckets only
```

**Note**: The `./deploy.sh` script handles all deployment dependencies automatically. No manual `pip install` required for deployment.

## 📚 Document Management

### **Local Document Processing Setup**

For running document processing scripts locally, install the required dependencies:

```bash
# Install script dependencies (separate from Lambda layer)
pip install -r scripts/requirements.txt
```

### **Document Processing Commands**

```bash
# Process documents locally (recommended)
python3 scripts/process_documents_locally.py --folder ./documents

# Process single document
python3 scripts/process_documents_locally.py --file ./doc.pdf

# Delete document
python3 scripts/process_documents_locally.py --delete "document-id"
```

### **Vector Index Management**

Maintain optimal performance with built-in vector management tools:

```bash
# Optimize vector index performance (recommended weekly)
./vector_manager.sh optimize chatbot-document-vectors

# Monitor performance and costs
./vector_manager.sh stats

# List all vector indexes with details
./vector_manager.sh list

# Clear caches after bulk document updates
./vector_manager.sh clear-cache
```

**Key Benefits:**
- ⚡ **Automatic optimization** - Clears caches and optimizes performance
- 📊 **Performance monitoring** - Track cache hit rates and costs
- 🔧 **Zero configuration** - Automatically detects deployment settings
- 💰 **Cost tracking** - Monitor monthly vector storage and query costs

## 💰 Estimated Costs

| Users/Day | Monthly Cost |
|-----------|--------------|
| 50        | $11          |
| 250       | $40          |
| 500       | $79          |

*Includes AI processing, hosting, vector storage, security, and 20% caching savings*

## 🏗️ Architecture

- **Frontend**: JavaScript widget with WebSocket support
- **Backend**: Python Lambda functions (Graviton3)
- **AI**: Amazon Nova Lite + Titan Embeddings
- **Storage**: S3 Vector buckets for embeddings
- **Security**: WAF, Guardrails, rate limiting
- **CDN**: CloudFront for global delivery
- **Caching**: Multi-layer response and context caching

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
- **[VECTOR_MANAGEMENT.md](VECTOR_MANAGEMENT.md)** - Vector index management guide
- **[docs/troubleshooting.md](docs/troubleshooting.md)** - Common issues
- **[docs/api-spec.yaml](docs/api-spec.yaml)** - API documentation

## 🆘 Need Help?

1. **Deployment Issues**: Check `deployment.log` and run `./deploy.sh status`
2. **Vector Management**: See [VECTOR_MANAGEMENT.md](VECTOR_MANAGEMENT.md) for optimization and troubleshooting
3. **General Issues**: Check [docs/troubleshooting.md](docs/troubleshooting.md)
4. **Vector Performance**: Run `./vector_manager.sh stats` to monitor performance

## 📄 License

MIT License - Free for commercial and personal use.

---

**Ready to deploy?**
```bash
./deploy.sh deploy
```

**Ready to optimize your vectors?**
```bash
./vector_manager.sh optimize chatbot-document-vectors
```
