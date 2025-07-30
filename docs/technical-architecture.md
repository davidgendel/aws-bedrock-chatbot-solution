# Technical Architecture - RAG Chatbot Solution

## 🏗️ System Overview

The RAG (Retrieval-Augmented Generation) Chatbot is a serverless, cloud-native solution built on AWS that provides intelligent conversational AI capabilities with document-based knowledge retrieval.

## 📊 Architecture Components

### Frontend Layer

#### CloudFront Distribution
- **Purpose**: Global content delivery network for chatbot widget
- **Configuration**: 
  - Origin: S3 bucket with website assets
  - Caching: Optimized for static assets (JS, HTML, CSS)
  - SSL/TLS: Automatic HTTPS enforcement
  - Global edge locations for low latency

#### Chatbot Widget (JavaScript)
- **File**: `src/frontend/widget.js` (52KB minified)
- **Features**:
  - WebSocket and REST API support
  - Client-side response caching
  - Real-time streaming interface
  - Mobile-responsive design
  - Accessibility compliance (WCAG 2.1)

### Security Layer

#### AWS WAF (Web Application Firewall)
- **Protection**: DDoS mitigation, bot filtering, rate limiting
- **Rules**:
  - IP-based rate limiting (100 requests/5 minutes)
  - Geographic restrictions (configurable)
  - SQL injection and XSS protection
  - Custom rule sets for API protection

#### API Authentication
- **REST API**: API key authentication via `x-api-key` header
- **WebSocket**: Connection-based authentication (no API key required)
- **Key Management**: AWS API Gateway managed keys

### API Layer

#### REST API Gateway
- **Endpoint**: `https://{api-id}.execute-api.{region}.amazonaws.com/prod/`
- **Methods**:
  - `POST /chat` - Non-streaming chat requests
  - `GET /health` - Health check endpoint
- **Features**:
  - Request/response validation
  - CORS configuration
  - Throttling and quotas
  - CloudWatch integration

#### WebSocket API Gateway
- **Endpoint**: `wss://{websocket-api-id}.execute-api.{region}.amazonaws.com/prod`
- **Routes**:
  - `$connect` - Connection establishment
  - `$disconnect` - Connection cleanup
  - `sendMessage` - Chat message handling
  - `heartbeat` - Connection keep-alive
- **Features**:
  - Real-time bidirectional communication
  - Connection state management
  - Automatic reconnection handling

### Compute Layer

#### Lambda Functions

##### Main Chat Function
- **Runtime**: Python 3.12 on Graviton3 processors
- **Memory**: 512 MB
- **Timeout**: 30 seconds
- **Concurrency**: 100 concurrent executions
- **Features**:
  - Handles both REST and WebSocket requests
  - Streaming response generation
  - Vector similarity search
  - Response caching
  - Error handling and logging

##### Document Processor Function
- **Runtime**: Python 3.12 on Graviton3 processors
- **Memory**: 1024 MB (for document processing)
- **Timeout**: 5 minutes
- **Features**:
  - Multi-format document parsing
  - Text extraction and chunking
  - Embedding generation
  - Metadata extraction

### AI/ML Services

#### Amazon Bedrock
- **Primary Model**: Amazon Nova Lite (`amazon.nova-lite-v1:0`)
  - Fast inference (< 2 seconds)
  - Cost-optimized for conversational AI
  - Support for streaming responses
  
- **Embedding Model**: Amazon Titan Embeddings (`amazon.titan-embed-text-v1`)
  - 1536-dimensional vectors
  - Optimized for semantic search
  - Batch processing support

- **Guardrails**: Content filtering and safety
  - PII detection and redaction
  - Harmful content filtering
  - Topic-based restrictions
  - Custom word filters

#### Amazon Textract
- **Purpose**: OCR and document analysis for images and scanned PDFs
- **Features**:
  - Text extraction from images
  - Table and form detection
  - Layout analysis
  - Multi-language support

### Storage Layer

#### S3 Buckets

##### Document Storage
- **Bucket**: `chatbot-documents-{account}-{region}`
- **Purpose**: Raw document storage
- **Supported Formats**: PDF, DOCX, TXT, MD, HTML, CSV, JSON, Images
- **Lifecycle**: Intelligent tiering for cost optimization

##### Vector Storage (Amazon S3 Vectors)
- **Service**: Amazon S3 Vectors (native vector support)
- **Index**: `chatbot-document-vectors`
- **Dimensions**: 1536 (Amazon Titan embeddings)
- **Similarity Metric**: Cosine similarity
- **Features**:
  - Native vector operations at cloud scale
  - HNSW indexing for fast similarity search
  - Automatic scaling and management
  - Built-in metadata filtering
  - Cost-optimized storage and retrieval

##### Website Assets
- **Bucket**: `chatbot-website-{account}-{region}`
- **Purpose**: Static assets (widget.js, demo pages)
- **CloudFront Origin**: Serves global content delivery

##### Metadata Storage
- **Bucket**: `chatbot-metadata-{account}-{region}`
- **Purpose**: Document processing metadata and analytics
- **Content**: Processing logs, usage statistics, error reports

### Monitoring and Logging

#### CloudWatch
- **Log Groups**:
  - `/aws/lambda/ChatbotRagStack-ChatbotFunction-*`
  - `/aws/lambda/ChatbotRagStack-DocumentProcessor-*`
  - Custom application logs with structured logging

- **Metrics**:
  - Request latency and throughput
  - Error rates and types
  - Vector search performance
  - Cost tracking

- **Alarms**:
  - High error rates (> 5%)
  - Increased latency (> 10 seconds)
  - Cost thresholds
  - Resource utilization

## 🔄 Data Flow

### Chat Request Flow (REST API)
1. User sends message via widget
2. CloudFront routes to API Gateway
3. WAF validates and filters request
4. API Gateway authenticates via API key
5. Lambda function processes request:
   - Validates input
   - Applies content guardrails
   - Generates query embedding
   - Searches vector storage
   - Constructs context prompt
   - Calls Bedrock for response
   - Caches response
6. Response returned to client

### Chat Request Flow (WebSocket)
1. Client establishes WebSocket connection
2. Connection authenticated and stored
3. User sends message via WebSocket
4. Lambda processes message (similar to REST)
5. Response streamed in chunks:
   - `{"type": "start"}` - Streaming begins
   - `{"type": "chunk", "text": "..."}` - Text chunks
   - `{"type": "end", "text": "complete response"}` - Final response
6. Connection maintained for subsequent messages

### Document Processing Flow
1. Document uploaded to S3 documents bucket
2. S3 event triggers Lambda function
3. Document processor:
   - Downloads document from S3
   - Determines format and processing method
   - Extracts text (Textract for images/PDFs)
   - Chunks text intelligently
   - Generates embeddings via Bedrock
   - Stores vectors and metadata in S3
4. Document ready for search queries

## 🔧 Vector Search Implementation

### Amazon S3 Vectors Implementation
- **Native Vector Operations**: Built-in vector storage and similarity search
- **Search Algorithm**: HNSW (Hierarchical Navigable Small World) indexing
- **Performance**: O(log n) search complexity with sub-second response times
- **Scalability**: Automatic scaling to handle millions of vectors
- **Cost Optimization**: Pay-per-use pricing with intelligent caching

### Search Process
1. Query text converted to embedding via Amazon Titan
2. S3 Vectors native similarity search with HNSW indexing
3. Metadata filtering applied for relevance
4. Top-k results retrieved with similarity scores
5. Results ranked by combined similarity and importance scores
6. Context assembled for prompt generation with source attribution

## 🛡️ Security Implementation

### Data Protection
- **Encryption in Transit**: HTTPS/WSS for all communications
- **Encryption at Rest**: S3 server-side encryption
- **API Security**: API key authentication, rate limiting
- **Content Filtering**: Bedrock Guardrails for input/output

### Access Control
- **IAM Roles**: Least privilege access for Lambda functions
- **Resource Policies**: S3 bucket policies restrict access
- **Network Security**: No VPC required (cost optimization)

## 📈 Performance Characteristics

### Latency
- **Cold Start**: ~2-3 seconds (first request)
- **Warm Response**: ~500ms-2s (cached Lambda)
- **Vector Search**: ~100-200ms
- **Bedrock Inference**: ~1-3 seconds
- **Streaming**: First chunk in ~1 second

### Throughput
- **Concurrent Users**: 100+ (Lambda concurrency limit)
- **Requests/Second**: 50+ per Lambda instance
- **Document Processing**: 10-20 documents/minute

### Scalability
- **Auto-scaling**: Serverless architecture scales to zero
- **Storage**: Unlimited S3 capacity
- **Global**: CloudFront edge locations worldwide

## 💰 Cost Optimization

### Serverless Benefits
- **No Idle Costs**: Pay only for actual usage
- **Auto-scaling**: No over-provisioning
- **Managed Services**: Reduced operational overhead

### Cost Breakdown (Monthly)
- **Lambda**: $5-15 (based on usage)
- **API Gateway**: $3-10 (per million requests)
- **S3 Storage**: $1-5 (documents and vectors)
- **Bedrock**: $10-50 (model inference)
- **CloudFront**: $1-5 (data transfer)
- **Total**: ~$20-85/month for typical usage

## 🔮 Future Enhancements

### Planned Improvements
1. **Native Vector Database**: Migration to Amazon OpenSearch or pgvector
2. **Async Processing**: SQS-based document processing pipeline
3. **Multi-tenancy**: Support for multiple organizations
4. **Advanced Analytics**: Usage patterns and optimization insights
5. **A/B Testing**: Model comparison and optimization

### Scalability Roadmap
1. **Caching Layer**: Redis/ElastiCache for response caching
2. **CDN Optimization**: Edge computing for faster responses
3. **Model Optimization**: Fine-tuned models for specific domains
4. **Batch Processing**: Improved document ingestion pipeline

This architecture provides a solid foundation for a production-ready RAG chatbot system with room for future enhancements and scaling.
