# RAG Chatbot - System Architecture

## 🏗️ System Overview

The RAG Chatbot is a serverless, cloud-native solution built on AWS that provides intelligent conversational AI with document-based knowledge retrieval.

## 📊 Architecture Diagram

```
                                    RAG Chatbot Solution Architecture

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Client Website │────▶│   CloudFront    │────▶│   S3 Bucket     │
│  with Embedded  │     │   Distribution  │     │   (Frontend     │
│  Widget         │     │   (Global CDN)  │     │   Assets)       │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
          │
          │ API Requests (REST + WebSocket)
          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   AWS WAF       │────▶│   API Gateway   │────▶│   Lambda        │
│   (DDoS/Bot     │     │   (REST + WS)   │     │   (Chat Logic)  │
│   Protection)   │     │   Rate Limiting │     │   with Streaming│
│                 │     │   API Keys      │     │   Nova Lite     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          │ Vector Search
                                                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   S3 Vectors    │◀────│   Lambda        │────▶│   Amazon        │
│   (Document     │     │   (Document     │     │   Bedrock       │
│   Embeddings)   │     │   Processor)    │     │   • Nova Lite   │
│   HNSW Index    │     │   Sync Process  │     │   • Titan Embed │
│                 │     │                 │     │   • Guardrails  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
          ▲                       ▲
          │                       │
          │ Store Embeddings      │ Process Documents
          │                       │
          │               ┌─────────────────┐     ┌─────────────────┐
          │               │                 │     │                 │
          └───────────────│   S3 Bucket     │◀────│   CloudWatch    │
                          │   (Documents)   │     │   (Monitoring   │
                          │   Multi-format  │     │   & Logging)    │
                          │   Support       │     │                 │
                          └─────────────────┘     └─────────────────┘
```

## 🔄 Data Flow

### 1. Document Processing Flow
- Upload → Extract text → Chunk → Generate embeddings → Store in S3 Vector buckets

### 2. Chat Request Flow
- User query → Generate embedding → Vector similarity search → Retrieve context → Generate response

### 3. Response Delivery Flow
- Stream response via WebSocket or return via REST API

## 📊 Architecture Components

### Frontend Layer
- **CloudFront Distribution**: Global CDN for chatbot widget with edge caching
- **JavaScript Widget**: WebSocket/REST API support with real-time streaming
- **S3 Static Hosting**: Reliable storage for frontend assets

### Security Layer
- **AWS WAF**: DDoS mitigation, rate limiting, bot filtering
- **API Authentication**: API key authentication via AWS API Gateway
- **Lambda Authorizers**: Custom authentication and authorization logic

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

## 🚀 Deployment Architecture

- **Infrastructure as Code**: AWS CDK (Python)
- **Atomic Deployment**: Rollback-capable deployment system
- **Multi-Environment**: Configurable for dev/staging/prod

## 📈 Scalability Features

- **Auto-scaling**: Lambda functions scale automatically with demand
- **Caching**: Multi-layer caching for embeddings and responses
- **HNSW Indexing**: Hierarchical vector search for large document sets
- **Global Distribution**: CloudFront handles worldwide traffic

## 🔒 Security Features

- **Encryption**: All data encrypted in transit and at rest
- **Network Security**: VPC endpoints, private subnets
- **Content Filtering**: Bedrock Guardrails for safe AI responses
- **Access Control**: IAM roles with minimal permissions
- **Request Signing**: AWS SigV4 for enhanced API security

## 💰 Cost Optimization

- **Graviton3 Processors**: 20% better price-performance
- **Provisioned Concurrency**: Optimized for consistent performance
- **S3 Lifecycle Policies**: Automatic cleanup of old data
- **Efficient Caching**: Reduces API calls and compute costs
- **Serverless Architecture**: Pay only for actual usage

## 🔧 Key Design Decisions

### Why S3 Vectors?
- **Serverless**: No database management overhead
- **Scalable**: Handles millions of vectors automatically
- **Cost-effective**: Pay only for storage used
- **HNSW Indexing**: Fast hierarchical search algorithm

### Why Amazon Nova Lite?
- **Cost-effective**: Optimized for price-performance
- **Fast responses**: Low latency for real-time chat
- **Streaming support**: Real-time response generation
- **Guardrails integration**: Built-in safety features

### Why Serverless Architecture?
- **Auto-scaling**: Handles traffic spikes automatically
- **Cost efficiency**: No idle resource costs
- **Maintenance-free**: AWS manages infrastructure
- **High availability**: Built-in redundancy and failover
