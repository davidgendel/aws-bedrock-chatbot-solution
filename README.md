# RAG Chatbot - 15-Minute AI Assistant for Your Business

> **⚠️ DISCLAIMER**: This project is an example of how you can design and deploy a small scale chatbot leveraging AWS services such as AWS Lambda, Amazon Bedrock, and AWS API Gateway. The focus in this example is on keeping costs as low as possible while also upholding strong security principles and protections. By deploying this project you will incur costs that will depend on your actual utilization. No support or warranty is provided. This example is not endorsed or supported by AWS.

Deploy a production-ready AI chatbot that learns from your documents in just 15 minutes. **Starting at $21.89/month**.

## 🚀 Quick Start

### One-Command Deployment (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/aws-bedrock-chatbot-solution/main/install.sh | bash
```

**⚠️ IMPORTANT**: Replace `YOUR_USERNAME` with your actual GitHub username.

### Manual Deployment
```bash
git clone https://github.com/YOUR_USERNAME/aws-bedrock-chatbot-solution.git
cd aws-bedrock-chatbot-solution
./deploy.sh deploy
```

### Deployment Commands
```bash
# Deploy the chatbot
./deploy.sh deploy

# Check deployment status
./deploy.sh status

# Rollback deployment (deletes AWS infrastructure)
./deploy.sh rollback

# Get help
./deploy.sh help
```

**📋 For complete deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)**

## ✨ What You Get

### 🤖 Smart AI Assistant
- **Amazon Nova Lite** for fast, accurate responses
- **RAG Technology** learns from your documents
- **Real-time streaming** responses
- **Content moderation** built-in
- **Multi-format document support** (PDF, Word, images, etc.)

### 🔒 Enterprise Security
- **AWS WAF** protection with DDoS mitigation
- **Rate limiting** and throttling
- **PII detection** and blocking
- **Automatic credential rotation**
- **Content filtering** with Bedrock Guardrails

### 📱 Easy Integration
- **Embeddable widget** for any website
- **Customizable themes** to match your brand
- **Mobile responsive** design
- **Accessibility compliant**
- **WebSocket support** for real-time chat

### 📊 Production Ready
- **Auto-scaling** serverless architecture
- **99.9% uptime** with AWS infrastructure
- **Monitoring** and alerting included
- **Backup and recovery** automated
- **Atomic deployment** with rollback capabilities

### ⚡ Performance Features
- **Amazon S3 Vectors** for native cloud vector storage
- **HNSW hierarchical indexing** for O(log n) search performance
- **NumPy SIMD acceleration** for 5-10x faster similarity calculations
- **Async batch processing** for high-throughput document ingestion
- **Multi-layer caching** for sub-second response times

## 💰 Estimated Costs

| Business Size | Daily Users | Monthly Cost | Cost per User |
|---------------|-------------|--------------|---------------|
| **Small** | 50 | **$21.89** | $0.44 |
| **Medium** | 250 | **$59.64** | $0.24 |
| **Growing** | 500 | **$115.01** | $0.23 |

*Includes everything: AI processing, hosting, vector storage, security, and monitoring*

📋 **[View Detailed Pricing Breakdown](docs/pricing.md)**

## 📋 Prerequisites

You need:
1. **AWS Account** (free to create)
2. **5 minutes** to set up AWS credentials
3. **Your business documents** (PDFs, Word docs, images, etc.)
4. **jq** (optional, for atomic deployment features)

The deployment script installs everything else automatically.

## 🧪 Test Your Chatbot

### Sample Demo Page
After deployment, test your chatbot using the included sample page:

**📄 Location**: `src/frontend/index.html`

```bash
# Open the sample page in your browser
open src/frontend/index.html
# or
firefox src/frontend/index.html
# or
chrome src/frontend/index.html
```

**✨ Features of the demo page:**
- **Interactive chatbot widget** with your deployed configuration
- **Test controls** to try caching, streaming, and WebSocket features
- **Example questions** to get started
- **Connection status** indicator
- **Performance testing** tools (cache clearing, reconnection)

**💡 Pro tip**: Use this sample page to validate your deployment and test new features before integrating into your website.

## 📚 Document Management Commands

### Local Document Processing (Recommended)
Documents are now processed locally with full functionality, then uploaded to S3:

```bash
# Install local processing dependencies
pip install -r requirements-local.txt

# Process a single document
python3 scripts/process_documents_locally.py --file ./my-document.pdf

# Process all documents in a folder
python3 scripts/process_documents_locally.py --folder ./documents

# Process folder recursively (includes subfolders)
python3 scripts/process_documents_locally.py --folder ./documents --recursive

# Process with custom document ID
python3 scripts/process_documents_locally.py --file ./doc.pdf --document-id "my-custom-id"

# Delete a processed document
python3 scripts/process_documents_locally.py --delete "document-id"

# Batch processing mode (faster for multiple files)
python3 scripts/process_documents_locally.py --folder ./documents --batch
```

### Legacy Upload Commands (for compatibility)
```bash
# Upload new documents (uses local processing)
python3 -m scripts.upload_documents --folder ./documents

# Upload a single document
python3 -m scripts.upload_documents --file ./my-document.pdf

# Upload documents in batch mode
python3 -m scripts.upload_documents --folder ./documents --batch
```

### System Management Commands
```bash
# Clean up old vectors (90+ days)
python3 scripts/cleanup_vectors.py --days 90

# Manage vector index for better performance
python3 scripts/manage_vector_indexes.py --rebuild

# View deployment status
aws cloudformation describe-stacks --stack-name ChatbotRagStack

# Check system health
./deploy.sh status

# Rollback deployment if needed
./deploy.sh rollback
```

## 🗑️ Uninstalling

To completely remove the chatbot and all AWS resources:

```bash
# Quick uninstall (recommended)
./deploy.sh rollback

# For manual uninstall steps, see the complete guide
```

**📋 [Complete Uninstall Guide](docs/uninstall-guide.md)**

## 🔧 Architecture

This solution uses a modern serverless architecture on AWS:

### Core Services
- **Amazon Nova Lite** for fast, cost-effective AI responses
- **Amazon Titan Embeddings** for document vectorization  
- **AWS Lambda** (Graviton3) for serverless compute with streaming
- **Amazon API Gateway** for REST and WebSocket APIs
- **AWS WAF** for security protection and DDoS mitigation
- **Amazon CloudFront** for global content delivery
- **Amazon S3** for document and vector storage
- **Amazon Textract** for OCR and document analysis

### Key Features
- **Real-time streaming** via WebSocket API
- **Custom vector search** with S3-based storage
- **Multi-format document support** (PDF, Word, images, etc.)
- **Content filtering** with Bedrock Guardrails
- **Global CDN** for worldwide performance
- **Serverless scaling** from 0 to thousands of requests

### Architecture Documentation
- 📋 **[Architecture Diagram](docs/architecture.txt)** - Visual system overview
- 🔧 **[Technical Architecture](docs/technical-architecture.md)** - Detailed implementation guide
- 📊 **[API Specification](docs/api-spec.yaml)** - Complete API documentation

## 📈 Features

### Document Processing
- **Multiple formats**: PDF, Word, text, markdown, HTML, CSV, JSON, images
- **Intelligent chunking** based on document structure
- **Metadata extraction** for better search
- **Automatic embedding** generation with batch processing
- **Async processing** for high-throughput ingestion

### Chat Interface
- **Streaming responses** for better UX
- **Client-side caching** to reduce costs
- **Suggested questions** based on content
- **Feedback collection** for improvement
- **WebSocket support** for real-time communication

### Security & Compliance
- **Content filtering** with Bedrock guardrails
- **PII detection** and blocking
- **Rate limiting** to prevent abuse
- **Comprehensive logging** for audit trails
- **WAF protection** against common attacks

### Monitoring & Analytics
- **Real-time dashboards** in CloudWatch
- **Cost tracking** and analysis
- **Performance metrics** and alerting
- **Usage analytics** for insights
- **Vector index statistics** and management

### Deployment & Operations
- **Atomic deployment** with automatic rollback
- **Checkpoint-based recovery** for failed deployments
- **Zero-downtime updates** with blue-green deployment
- **Comprehensive error analysis** and recovery suggestions
- **State management** for deployment tracking

## 🔄 Development

### Running Tests
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
python3 run_tests.py

# Run specific test types
python3 run_tests.py --type unit
python3 run_tests.py --type integration
```

### Configuration Validation
```bash
# Validate configuration
python3 src/backend/config_validator.py config.json
```

### Local Development
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run configuration validation
python3 src/backend/config_validator.py

# Run tests with coverage
python3 run_tests.py --install-deps --coverage
```

### Performance Testing
```bash
# Test vector similarity performance
python3 -c "
from src.backend.s3_vector_utils import calculate_batch_cosine_similarity
import numpy as np
import time

# Generate test vectors
query = np.random.rand(1536).tolist()
vectors = [np.random.rand(1536).tolist() for _ in range(1000)]

# Benchmark batch processing
start = time.time()
similarities = calculate_batch_cosine_similarity(query, vectors)
end = time.time()

print(f'Processed 1000 vectors in {end-start:.3f}s')
print(f'Throughput: {1000/(end-start):.0f} vectors/second')
"
```

## 🆘 Need Help?

### Common Issues
- **Deployment failed?** Run `./deploy.sh rollback` and try again
- **AWS permissions?** Check [DEPLOYMENT.md](DEPLOYMENT.md)
- **Chatbot not responding?** See [docs/troubleshooting.md](docs/troubleshooting.md)
- **Performance issues?** Run vector index rebuild

### Get Support
- 📖 [Complete Deployment Guide](DEPLOYMENT.md)
- 📖 [Documentation](docs/)
- ❓ [FAQ](docs/faq.md)
- 🔧 [Troubleshooting Guide](docs/troubleshooting.md)

## 📄 License

MIT License - Use for commercial and personal projects.

---
