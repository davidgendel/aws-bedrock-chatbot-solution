# RAG Chatbot - AI Assistant Example Project

> **⚠️ EXAMPLE PROJECT**: This demonstrates how to build a RAG chatbot using AWS services. Costs will vary based on usage. No warranty provided.

Deploy an AI chatbot that learns from your documents in 15-20 minutes. **Starting at $11/month**.

## 🚀 Quick Start

```bash
git clone https://github.com/your-github-username/aws-bedrock-chatbot-solution.git
cd aws-bedrock-chatbot-solution
./chatbot deploy
```

**⚠️ Replace `your-github-username` with your actual GitHub username**


## ✨ Features

- **Amazon Nova Lite** for fast AI responses
- **S3 Vectors** for scalable document embeddings storage
- **AWS Request Signing** with SigV4 for enhanced security
- **One-command vector optimization** with built-in performance monitoring
- **Real-time streaming** via WebSocket
- **Content moderation** with Bedrock Guardrails
- **Multi-format documents** (PDF, DOCX, TXT, MD, HTML, CSV, JSON)
- **Enterprise security** (WAF, rate limiting, PII detection, signed requests)
- **Auto-scaling** serverless architecture
- **Multi-layer caching** for 20% cost savings

## 📋 Prerequisites

- AWS Account with appropriate permissions
- AWS CLI 2.27+ configured (`aws configure`)
- Python 3.12+ installed
- Python venv installed
- Node 22+ installed
- Git installed
- Docker installed

## 🛠️ Commands

```bash
./chatbot validate        # Validate environment before deployment
./chatbot deploy          # Deploy chatbot (no pip install needed)
./chatbot status          # Check status
./chatbot rollback        # Remove deployment
./chatbot cleanup --s3-only # Empty S3 buckets only
```

**Note**: The `./chatbot` script handles all deployment dependencies automatically. No manual `pip install` required for deployment.

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
./chatbot vector optimize

# Monitor performance and costs
./chatbot vector stats

# List all vector indexes with details
./chatbot vector list

# Clear caches after bulk document updates
./chatbot vector clear-cache
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

For detailed architecture information, see [Architecture Guide](docs/architecture.md).

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
- **[docs/vector_management.md](docs/vector_management.md)** - Vector index management guide
- **[docs/request-signing.md](docs/request-signing.md)** - AWS request signing configuration
- **[docs/troubleshooting.md](docs/troubleshooting.md)** - Common issues
- **[docs/api-spec.yaml](docs/api-spec.yaml)** - API documentation

## 🆘 Need Help?

1. **Deployment Issues**: Check `deployment.log` and run `./chatbot status`
2. **Vector Management**: See [docs/vector_management.md](docs/vector_management.md) for optimization and troubleshooting
3. **General Issues**: Check [docs/troubleshooting.md](docs/troubleshooting.md)
4. **Vector Performance**: Run `./chatbot vector stats` to monitor performance

## 📄 License

MIT License - Free for commercial and personal use.

---

**Ready to deploy?**
```bash
./chatbot deploy
```

**Ready to optimize your vectors?**
```bash
./chatbot vector optimize
```
