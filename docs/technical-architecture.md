# Technical Architecture - RAG Chatbot

## 🏗️ System Overview

The RAG Chatbot is a serverless, cloud-native solution built on AWS that provides intelligent conversational AI with document-based knowledge retrieval.

## 📊 Architecture Components

### Frontend Layer
- **CloudFront Distribution**: Global CDN for chatbot widget
- **JavaScript Widget**: WebSocket/REST API support with real-time streaming

### Security Layer
- **AWS WAF**: DDoS mitigation, rate limiting, bot filtering
- **API Authentication**: API key authentication via AWS API Gateway

### API Layer
- **REST API Gateway**: Non-streaming chat requests, health checks
- **WebSocket API Gateway**: Real-time bidirectional communication

### Compute Layer
- **Lambda Functions**: Python 3.12 on Graviton3 processors
  - Main Chat Function: 512 MB, 30s timeout
  - Document Processor: 1024 MB, 5min timeout

### AI/ML Services
- **Amazon Bedrock**:
  - Primary Model: Amazon Nova Lite (`amazon.nova-lite-v1:0`)
  - Embedding Model: Amazon Titan Embeddings (`amazon.titan-embed-text-v2:0`)
  - Guardrails: Content filtering and safety

### Storage Layer
- **S3 Vector Buckets**: Document embeddings with HNSW vector search
- **S3 Standard Buckets**: Document storage and metadata
- **CloudWatch Logs**: Application logs and monitoring

### Monitoring & Security
- **CloudWatch**: Metrics, alarms, and dashboards
- **WAF Rules**: Rate limiting, geographic restrictions
- **IAM Roles**: Least-privilege access control

## 🔄 Data Flow

1. **Document Processing**:
   - Upload → Extract text → Chunk → Generate embeddings → Store in S3 Vector buckets

2. **Chat Request**:
   - User query → Generate embedding → Vector similarity search → Retrieve context → Generate response

3. **Response Delivery**:
   - Stream response via WebSocket or return via REST API

## 🚀 Deployment Architecture

- **Infrastructure as Code**: AWS CDK (Python)
- **Atomic Deployment**: Rollback-capable deployment system
- **Multi-Environment**: Configurable for dev/staging/prod

## 📈 Scalability

- **Auto-scaling**: Lambda functions scale automatically
- **Caching**: Multi-layer caching for embeddings and responses
- **HNSW Indexing**: Hierarchical vector search for large document sets

## 🔒 Security Features

- **Encryption**: All data encrypted in transit and at rest
- **Network Security**: VPC endpoints, private subnets
- **Content Filtering**: Bedrock Guardrails for safe AI responses
- **Access Control**: IAM roles with minimal permissions

## 💰 Cost Optimization

- **Graviton3 Processors**: 20% better price-performance
- **Provisioned Concurrency**: Optimized for consistent performance
- **S3 Lifecycle Policies**: Automatic cleanup of old data
- **Efficient Caching**: Reduces API calls and compute costs
