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
- Python venv installed (`python3-venv` package)
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

**Note**: The `./chatbot` and `./process_documents` scripts handle all dependencies automatically using isolated Python virtual environments. No manual `pip install` required.


## 📚 Document Management

### **Document Processing Commands**

All commands automatically manage Python virtual environments to protect your system:

```bash
# Process documents in a folder
./process_documents --folder ./documents

# Parallel processing  
./process_documents --folder ./documents --parallel --workers 3

# Advanced parallel processing  
./process_documents --folder ./documents --advanced

# Process single document
./process_documents --file ./doc.pdf

# Delete document
./process_documents --delete "document-id"

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

### **Sample Documents for RAG**

This project includes four example documents to test out the chatbot. These are included for quick and easy testing, however you can use any compatible documents you want to test.


The folder **rag-docs** includes the following four historical novels in text format: Grimm's Fairy Tales, Moby Dick, The Count of Monte Cristo, and Frankenstein. These novels are in the public domain in the United States and are great examples to start with.

```bash
# Navigate to the project folder
cd aws-bedrock-chatbot-solution

# Run the processing for documents in a folder
./process_documents --folder ./rag-docs --advanced

```


**Key Benefits:**
- ⚡ **Automatic optimization** - Clears caches and optimizes performance
- 📊 **Performance monitoring** - Track cache hit rates and costs
- 💰 **Cost tracking** - Monitor monthly vector storage and query costs

## 💰 Estimated Costs

### Cost Breakdown by Usage Scenario

| Scenario | Daily Users | Interactions/User | Avg Tokens | Monthly Cost |
|----------|-------------|-------------------|------------|--------------|
| **Light** | 50 | 15 | 400 | **$11** |
| **Medium** | 250 | 18 | 500 | **$40** |
| **Heavy** | 500 | 20 | 600 | **$79** |

### Detailed Cost Components (Medium Scenario)

| Service | Monthly Cost | Description |
|---------|--------------|-------------|
| **Nova Lite AI** | $19.04 | Input ($2.84) + Output ($16.20) tokens |
| **Titan Embeddings** | $0.81 | Document vectorization |
| **Lambda Functions** | $8.50 | ARM64 with provisioned concurrency |
| **S3 + CloudFront** | $4.50 | Vector storage + global CDN |
| **WAF + Guardrails** | $3.20 | Security and content filtering |
| **API Gateway** | $0.47 | REST + WebSocket APIs |
| **Monitoring** | $3.48 | CloudWatch metrics and logs |
| **Total** | **$40.00** | *Includes 20% caching savings* |

### Current AWS Pricing Basis (US East 1)
- **Nova Lite**: $0.06 per 1K input tokens, $0.24 per 1K output tokens
- **Titan Embeddings v2**: ~$0.10 per 1K tokens
- **Lambda ARM64**: $0.0000133334 per GB-second + provisioned concurrency
- **S3 Vectors**: Standard S3 pricing + vector index operations
- **API Gateway**: $3.50 per million requests
- **CloudFront**: $0.085 per GB (first 10TB tier)

### Key Cost Optimizations
- ⚡ **ARM64 Lambda**: 20% better price/performance than x86
- 🎯 **Nova Lite**: Most cost-effective Bedrock model
- 💾 **S3 Vectors**: 60% cheaper than managed vector databases
- 🚀 **Multi-layer caching**: 20% reduction in AI model calls
- 📊 **Provisioned concurrency**: Only 1 unit to minimize cold starts

*All estimates based on current AWS pricing (US East 1) and include security, monitoring, and global CDN delivery.*

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
