# RAG Chatbot User Guide

This comprehensive guide provides detailed instructions for setting up, configuring, and using the enhanced RAG Chatbot solution with S3 Vectors and atomic deployment.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Deployment Options](#deployment-options)
3. [Configuration](#configuration)
4. [Managing Your Knowledge Base](#managing-your-knowledge-base)
5. [Customizing the Widget](#customizing-the-widget)
6. [Performance Optimization](#performance-optimization)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)
9. [Advanced Features](#advanced-features)

## Getting Started

### Prerequisites

Before deploying the RAG Chatbot solution, ensure you have:

**Required:**
1. **AWS Account**: An AWS account with appropriate permissions
2. **AWS CLI**: Installed and configured with credentials (`aws configure`)
3. **Python 3.12+**: Version 3.9 minimum, 3.12+ recommended
4. **Git**: For cloning the repository

**Optional (Enhanced Features):**
5. **jq**: For atomic deployment with rollback capabilities
6. **scikit-learn**: Auto-installed for vector clustering optimization

### System Requirements

- **Operating System**: Linux, macOS, or Windows with WSL
- **Memory**: At least 4GB RAM (8GB recommended)
- **Disk Space**: At least 2GB free space
- **Network**: Stable internet connection

### Quick Setup Verification

```bash
# Verify prerequisites
python3 --version    # Should be 3.12+
aws --version       # Should be 2.27.51+
git --version       # Should be installed
jq --version        # Optional, for atomic deployment
node --version      # Should be 22.0+

# Test AWS credentials
aws sts get-caller-identity
```

## Deployment Options

### Option 1: One-Command Deployment (Recommended for Beginners)

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/aws-bedrock-chatbot-solution/main/install.sh | bash
```

**Features:**
- ✅ Fully automated setup
- ✅ Dependency installation
- ✅ Error recovery
- ✅ Integration code generation

**Time**: 15-20 minutes

### Option 2: Atomic Deployment (Recommended for Production)

```bash
git clone https://github.com/YOUR_USERNAME/aws-bedrock-chatbot-solution.git
cd chatbot-rag
./deploy.sh deploy
```

**Features:**
- ✅ Automatic rollback on failure
- ✅ Checkpoint-based recovery
- ✅ Comprehensive error analysis
- ✅ State management
- ✅ Zero-downtime updates

**Time**: 18-25 minutes

### Option 3: Standard Manual Deployment

```bash
git clone https://github.com/YOUR_USERNAME/aws-bedrock-chatbot-solution.git
cd chatbot-rag
./deploy.sh
```

**Features:**
- ✅ Full control over process
- ✅ Basic error recovery
- ✅ Faster deployment

**Time**: 15-20 minutes

## Configuration

### Environment Configuration

The system uses several configuration methods:

#### 1. Configuration File (config.json)

```json
{
  "deployment": {
    "region": "us-east-1",
    "environment": "production",
    "atomic_deployment": true
  },
  "vector_storage": {
    "provider": "s3_vectors",
    "index_type": "hnsw",
    "dimensions": 1536,
    "similarity_metric": "cosine"
  },
  "performance": {
    "enable_caching": true,
    "batch_processing": true,
    "async_processing": true,
    "max_batch_size": 10
  },
  "security": {
    "enable_waf": true,
    "content_filtering": true,
    "pii_detection": true,
    "rate_limit_per_minute": 60
  },
  "ai_models": {
    "chat_model": "amazon.nova-lite-v1:0",
    "embedding_model": "amazon.titan-embed-text-v1",
    "enable_guardrails": true
  }
}
```

#### 2. Environment Variables

```bash
# Core Configuration
export VECTOR_BUCKET_NAME="your-vector-bucket"
export VECTOR_INDEX_NAME="chatbot-index"
export DOCUMENT_BUCKET_NAME="your-document-bucket"

# Performance Settings
export USE_ASYNC_PROCESSING=true
export MAX_BATCH_SIZE=10
export VECTOR_CACHE_SIZE=1000
export ENABLE_CACHING=true

# Security Settings
export ENABLE_CONTENT_FILTERING=true
export RATE_LIMIT_PER_MINUTE=60

# Debug Settings
export DEBUG=false
export LOG_LEVEL=INFO
```

#### 3. Runtime Configuration

```bash
# Validate configuration
python3 src/backend/config_validator.py config.json

# Test configuration
python3 -c "
from src.backend.config_validator import validate_config
result = validate_config('config.json')
print('Configuration valid:', result['valid'])
if not result['valid']:
    print('Errors:', result['errors'])
"
```

## Managing Your Knowledge Base

### Supported Document Formats

The system supports a wide range of document formats:

**Text Documents:**
- **PDF**: Including scanned PDFs with OCR
- **Microsoft Word**: DOCX format
- **Plain Text**: TXT files
- **Markdown**: MD files

**Web & Data Formats:**
- **HTML**: Web pages and documentation
- **CSV**: Structured data files
- **JSON**: Configuration and data files

**Images (with OCR):**
- **PNG, JPG, JPEG**: Standard image formats
- **TIFF**: High-quality document scans

### Document Upload Methods

#### Batch Upload (Recommended)

```bash
# Upload entire folder
python3 -m scripts.upload_documents --folder ./documents

# Upload specific file types only
python3 -m scripts.upload_documents --folder ./docs --types pdf,docx,txt

# Batch processing with custom size
python3 -m scripts.upload_documents --folder ./docs --batch-size 5

# Upload with progress tracking
python3 -m scripts.upload_documents --folder ./docs --verbose
```

#### Single Document Upload

```bash
# Upload single file
python3 -m scripts.upload_documents --file document.pdf

# Upload with custom metadata
python3 -m scripts.upload_documents --file document.pdf --metadata '{"category": "manual", "version": "1.0"}'
```

#### Programmatic Upload

```python
from scripts.upload_documents import upload_document, upload_folder

# Upload single document
result = upload_document("path/to/document.pdf")
print(f"Document ID: {result['document_id']}")
print(f"Status: {result['status']}")

# Upload folder with options
results = upload_folder(
    folder_path="./documents",
    file_types=["pdf", "docx", "txt"],
    batch_size=5
)
print(f"Uploaded {len(results)} documents")
```

### Document Processing Status

```bash
# Check overall processing status
python3 -c "
from src.backend.document_processor import handler
result = handler({'action': 'status'}, None)
print('Processing status:', result['body'])
"

# Check specific document status
python3 -c "
from src.backend.s3_vector_utils import get_document_status
status = get_document_status('document-id-here')
print('Document status:', status)
"

# List all processed documents
python3 -c "
from src.backend.s3_vector_utils import list_documents
docs = list_documents()
for doc in docs[:10]:  # Show first 10
    print(f'{doc[\"id\"]}: {doc[\"title\"]} ({doc[\"status\"]})')
"
```

### Document Management Commands

```bash
# List all documents
python3 -c "
from src.backend.s3_vector_utils import list_documents
docs = list_documents()
print(f'Total documents: {len(docs)}')
"

# Delete specific document
python3 -c "
from src.backend.s3_vector_utils import delete_document
result = delete_document('document-id-here')
print('Deletion result:', result)
"

# Clean up old documents (90+ days)
python3 scripts/cleanup_vectors.py --days 90

# Reprocess failed documents
python3 -c "
from src.backend.document_processor import reprocess_failed_documents
result = reprocess_failed_documents()
print('Reprocessing result:', result)
"
```

## Customizing the Widget

### Basic Integration

Add this code to your website:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Your Website</title>
</head>
<body>
    <!-- Your website content -->
    
    <!-- Chatbot Widget -->
    <div id="chatbot-widget"></div>
    <script src="https://your-cloudfront-domain/widget.js"></script>
    <script>
        ChatbotWidget.init({
            containerId: 'chatbot-widget',
            apiEndpoint: 'https://your-api-endpoint',
            title: 'Ask me anything!',
            placeholder: 'Type your question here...',
            theme: 'light'
        });
    </script>
</body>
</html>
```

### Advanced Customization

```javascript
ChatbotWidget.init({
    // Basic Configuration
    containerId: 'chatbot-widget',
    apiEndpoint: 'https://your-api-endpoint',
    
    // Appearance
    title: 'AI Assistant',
    subtitle: 'Powered by your knowledge base',
    placeholder: 'Ask me anything about our products...',
    theme: 'light', // 'light', 'dark', or 'auto'
    
    // Behavior
    autoOpen: false,
    showTypingIndicator: true,
    enableSuggestions: true,
    maxMessages: 50,
    
    // Styling
    primaryColor: '#007bff',
    backgroundColor: '#ffffff',
    textColor: '#333333',
    borderRadius: '8px',
    
    // Features
    enableFileUpload: false,
    enableFeedback: true,
    enableHistory: true,
    
    // Callbacks
    onMessageSent: function(message) {
        console.log('Message sent:', message);
    },
    onMessageReceived: function(response) {
        console.log('Response received:', response);
    },
    onError: function(error) {
        console.error('Chatbot error:', error);
    }
});
```

### Custom Themes

```css
/* Custom CSS for dark theme */
.chatbot-widget.dark-theme {
    --primary-color: #4a90e2;
    --background-color: #2c3e50;
    --text-color: #ecf0f1;
    --border-color: #34495e;
    --input-background: #34495e;
    --message-user-bg: #4a90e2;
    --message-bot-bg: #34495e;
}

/* Custom CSS for branded theme */
.chatbot-widget.branded-theme {
    --primary-color: #ff6b35;
    --background-color: #ffffff;
    --text-color: #2c3e50;
    --border-color: #ff6b35;
    --border-radius: 12px;
    font-family: 'Your Brand Font', sans-serif;
}
```

## Performance Optimization

### Vector Index Optimization

```bash
# Optimize vector index for better search performance
python3 scripts/manage_vector_indexes.py --optimize

# Check optimization status
python3 scripts/manage_vector_indexes.py --status

# Get index statistics
python3 scripts/manage_vector_indexes.py --stats

# Health check
python3 scripts/manage_vector_indexes.py --health-check
```

### Cache Management

```bash
# Check cache performance
python3 -c "
from src.backend.cache_manager import get_cache_stats
stats = get_cache_stats()
print(f'Cache hit rate: {stats[\"hit_rate\"]:.2%}')
print(f'Cache size: {stats[\"size\"]} items')
print(f'Memory usage: {stats[\"memory_mb\"]:.1f} MB')
"

# Clear cache if needed
python3 -c "
from src.backend.cache_manager import clear_cache
result = clear_cache()
print('Cache cleared:', result)
"

# Warm up cache with common queries
python3 -c "
from src.backend.cache_manager import warm_cache
queries = ['What is your return policy?', 'How do I contact support?']
result = warm_cache(queries)
print('Cache warmed up:', result)
"
```

### Performance Monitoring

```bash
# Monitor Lambda performance
aws logs filter-log-events \
    --log-group-name /aws/lambda/ChatbotFunction \
    --filter-pattern "REPORT" \
    --limit 10

# Check API Gateway metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApiGateway \
    --metric-name Latency \
    --dimensions Name=ApiName,Value=ChatbotApi \
    --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average,Maximum

# Benchmark vector search performance
python3 -c "
import time
from src.backend.s3_vector_utils import query_similar_vectors
import numpy as np

# Generate test query
query_embedding = np.random.rand(1536).tolist()

# Benchmark search
start = time.time()
results = query_similar_vectors(query_embedding, limit=10)
end = time.time()

print(f'Search completed in {end-start:.3f}s')
print(f'Found {len(results)} results')
"
```

## Monitoring and Maintenance

### Health Monitoring

```bash
# Overall system health check
./deploy.sh status

# API health check
curl -X GET https://your-api-endpoint/health

# Vector index health
python3 scripts/manage_vector_indexes.py --health-check

# Document processing health
python3 -c "
from src.backend.document_processor import handler
result = handler({'action': 'health'}, None)
print('Document processor health:', result['body'])
"
```

### Log Analysis

```bash
# View recent Lambda logs
aws logs tail /aws/lambda/ChatbotFunction --follow

# Search for errors
aws logs filter-log-events \
    --log-group-name /aws/lambda/ChatbotFunction \
    --filter-pattern "ERROR" \
    --start-time $(date -d '1 hour ago' +%s)000

# Search for performance issues
aws logs filter-log-events \
    --log-group-name /aws/lambda/ChatbotFunction \
    --filter-pattern "[timestamp, requestId, level=WARN]" \
    --start-time $(date -d '1 day ago' +%s)000
```

### Regular Maintenance Tasks

```bash
# Weekly maintenance script
#!/bin/bash

echo "Starting weekly maintenance..."

# 1. Clean up old vectors
python3 scripts/cleanup_vectors.py --days 90

# 2. Optimize vector indexes
python3 scripts/manage_vector_indexes.py --optimize

# 3. Check system health
./deploy.sh status

# 4. Update dependencies (if needed)
# Only needed for local script usage
pip install -r scripts/requirements.txt --upgrade

# 5. Generate maintenance report
python3 -c "
from src.backend.s3_vector_utils import get_index_stats
from src.backend.cache_manager import get_cache_stats

print('=== Weekly Maintenance Report ===')
print('Vector Index Stats:', get_index_stats())
print('Cache Stats:', get_cache_stats())
print('Maintenance completed successfully!')
"

echo "Weekly maintenance completed!"
```

### Cost Monitoring

```bash
# Check current month costs
aws ce get-cost-and-usage \
    --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
    --granularity MONTHLY \
    --metrics BlendedCost

# Set up cost alerts (run once)
aws budgets create-budget \
    --account-id $(aws sts get-caller-identity --query Account --output text) \
    --budget '{
        "BudgetName": "ChatbotMonthlyCost",
        "BudgetLimit": {
            "Amount": "100.00",
            "Unit": "USD"
        },
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST"
    }'
```

## Troubleshooting

### Common Issues and Solutions

#### Issue: Slow Response Times

```bash
# Check vector index optimization
python3 scripts/manage_vector_indexes.py --status

# If not optimized, run optimization
python3 scripts/manage_vector_indexes.py --optimize

# Check cache performance
python3 -c "
from src.backend.cache_manager import get_cache_stats
stats = get_cache_stats()
if stats['hit_rate'] < 0.5:
    print('Low cache hit rate - consider cache warming')
else:
    print('Cache performance is good')
"
```

#### Issue: High Memory Usage

```bash
# Enable async processing to reduce memory usage
export USE_ASYNC_PROCESSING=true

# Reduce batch size
export MAX_BATCH_SIZE=5

# Check memory usage patterns
python3 -c "
import psutil
import gc
from src.backend.s3_vector_utils import query_similar_vectors

print('Memory before:', psutil.Process().memory_info().rss / 1024 / 1024, 'MB')
results = query_similar_vectors([0.1] * 1536, limit=10)
print('Memory after:', psutil.Process().memory_info().rss / 1024 / 1024, 'MB')
gc.collect()
print('Memory after GC:', psutil.Process().memory_info().rss / 1024 / 1024, 'MB')
"
```

#### Issue: Document Processing Failures

```bash
# Check processing status
python3 -c "
from src.backend.document_processor import handler
result = handler({'action': 'status'}, None)
print('Processing status:', result['body'])
"

# Reprocess failed documents
python3 -c "
from src.backend.document_processor import reprocess_failed_documents
result = reprocess_failed_documents()
print('Reprocessing result:', result)
"

# Check supported file types
python3 -c "
from src.backend.document_processor import handler
result = handler({'action': 'supported_types'}, None)
print('Supported types:', result['body']['supported_file_types'])
"
```

### Getting Help

1. **Check Documentation**: Review [FAQ](faq.md) and [Troubleshooting Guide](troubleshooting.md)
2. **Run Diagnostics**: Use built-in diagnostic tools
3. **Check Logs**: Review deployment and runtime logs
4. **Community Support**: GitHub Issues for community help

## Advanced Features

### Custom AI Models

```python
# Configure custom models in config.json
{
    "ai_models": {
        "chat_model": "amazon.nova-pro-v1:0",  # More powerful model
        "embedding_model": "amazon.titan-embed-text-v2",  # Latest embedding model
        "enable_guardrails": true,
        "temperature": 0.7,
        "max_tokens": 2048
    }
}
```

### API Integration

```python
import requests

# Direct API usage
def query_chatbot(message, session_id=None):
    response = requests.post(
        'https://your-api-endpoint/chat',
        json={
            'message': message,
            'session_id': session_id or 'default',
            'stream': False
        },
        headers={'Content-Type': 'application/json'}
    )
    return response.json()

# Example usage
result = query_chatbot("What is your return policy?")
print(result['response'])
```

### Webhook Integration

```python
# Set up webhook for document processing notifications
def setup_webhook():
    webhook_config = {
        'url': 'https://your-domain.com/webhook',
        'events': ['document.processed', 'document.failed'],
        'secret': 'your-webhook-secret'
    }
    
    # Configure webhook in your system
    # This would be implemented based on your specific needs
```

---

## Summary

This user guide covers all aspects of the enhanced RAG Chatbot solution. Key features include:

- **S3 Vectors**: Native cloud vector storage with HNSW indexing
- **Atomic Deployment**: Rollback-capable deployment system
- **Performance Optimization**: Multiple optimization strategies
- **Comprehensive Monitoring**: Health checks and performance metrics
- **Flexible Configuration**: Multiple configuration methods
- **Advanced Customization**: Widget themes and API integration

For additional help, refer to the [FAQ](faq.md), [Troubleshooting Guide](troubleshooting.md), or check the project's GitHub repository.

1. Edit the `config.json` file to set your preferences
2. Run the deployment script:
   ```bash
   ./deploy.sh
   ```

### Verifying Deployment

After deployment completes:

1. Run the test script to verify all components are working:
   ```bash
   node scripts/test-deployment.js
   ```
2. Visit the demo page at the CloudFront URL provided in the deployment output
3. Try asking a few test questions to ensure the chatbot is responding correctly

## Configuration

### Configuration File

The `config.json` file contains all the configuration options for the solution:

```json
{
  "region": "us-east-1",
  "bedrock": {
    "modelId": "amazon.nova-lite-v1",
    "guardrails": {
      "createDefault": true
    }
  },
  "database": {
    "instanceType": "db.t4g.micro",
    "allocatedStorage": 20
  },
  "api": {
    "throttling": {
      "ratePerMinute": 10,
      "ratePerHour": 100
    }
  },
  "lambda": {
    "chatbot": {
      "provisionedConcurrency": {
        "enabled": true,
        "concurrentExecutions": 1
      }
    }
  },
  "widget": {
    "defaultTheme": {
      "primaryColor": "#4287f5",
      "secondaryColor": "#f5f5f5",
      "fontFamily": "Arial, sans-serif",
      "fontSize": "16px",
      "borderRadius": "8px"
    }
  }
}
```

### Key Configuration Options

- **region**: AWS region for deployment
- **bedrock.modelId**: Bedrock model to use for text generation
- **database.instanceType**: RDS instance type
- **lambda.chatbot.provisionedConcurrency**: Lambda provisioned concurrency settings
- **widget.defaultTheme**: Default appearance settings for the widget

## Managing Your Knowledge Base

### Adding Documents

To add documents to your knowledge base:

1. Create a folder for your documents:
   ```bash
   mkdir documents
   ```

2. Add your documents to the folder (supported formats: PDF, TXT, MD, HTML, CSV, JSON, PNG, JPG)

3. Upload the documents:
   ```bash
   npm run upload-docs -- --folder ./documents
   ```

### Document Processing

When you upload documents:

1. The system extracts text using Amazon Textract for PDFs and images
2. Documents are split into chunks using semantic boundaries
3. Vector embeddings are generated for each chunk
4. Chunks and embeddings are stored in the database

### Updating Documents

To update existing documents:

1. Upload a new version with the same filename
2. The system will automatically replace the old version

### Removing Documents

To remove documents from your knowledge base:

1. Delete the document from the S3 bucket using the AWS Console or CLI
2. Run the cleanup script to remove associated database entries:
   ```bash
   npm run cleanup-docs -- --key document-name.pdf
   ```

## Customizing the Widget

### Basic Integration

Add this code to your HTML page:

```html
<script src="https://your-cloudfront-distribution.cloudfront.net/widget.js"></script>
<script>
  SmallBizChatbot.init({
    containerId: 'chatbot-container'
  });
</script>
<div id="chatbot-container"></div>
```

### Customizing Appearance

```html
<script>
  SmallBizChatbot.init({
    containerId: 'chatbot-container',
    theme: {
      primaryColor: '#FF5733',
      secondaryColor: '#F8F9FA',
      fontFamily: 'Roboto, sans-serif',
      fontSize: '18px',
      borderRadius: '12px'
    },
    welcomeMessage: 'Hello! I\'m your company\'s AI assistant. How can I help you today?',
    placeholderText: 'Type your question here...'
  });
</script>
```

### Advanced Configuration

```html
<script>
  SmallBizChatbot.init({
    containerId: 'chatbot-container',
    streaming: true,
    cache: {
      enabled: true,
      maxEntries: 50,
      ttl: 7200000 // 2 hours in milliseconds
    },
    websocket: {
      reconnectAttempts: 3,
      reconnectInterval: 2000,
      connectionTimeout: 10000,
      heartbeatInterval: 60000
    },
    mobileToggle: true,
    suggestedQuestions: true,
    feedback: true,
    accessibility: {
      announcements: true,
      highContrast: false
    }
  });
</script>
```

### JavaScript API

```javascript
// Get chat history
const history = SmallBizChatbot.getHistory();

// Clear cache
SmallBizChatbot.clearCache();

// Enable/disable caching
SmallBizChatbot.setCacheEnabled(true);

// Enable/disable streaming
SmallBizChatbot.setStreamingEnabled(true);

// Get connection state
const state = SmallBizChatbot.getConnectionState();

// Manually reconnect WebSocket
SmallBizChatbot.reconnectWebSocket();
```

## Monitoring and Maintenance

### CloudWatch Dashboards

The solution creates two CloudWatch dashboards:

1. **ChatbotMonitoring**: Overall system monitoring
2. **BedrockPromptCacheMonitoring**: Bedrock prompt cache performance

To access these dashboards:

1. Open the AWS Console
2. Navigate to CloudWatch > Dashboards
3. Select the dashboard you want to view

### CloudWatch Alarms

The solution sets up the following alarms:

1. **ApiErrorRateAlarm**: Triggers when API Gateway 5XX errors exceed threshold
2. **LambdaErrorAlarm**: Triggers when Lambda function errors exceed threshold
3. **DatabaseCpuAlarm**: Triggers when database CPU utilization is too high

### Log Groups

The solution uses tiered log retention:

1. **Critical Logs**: Kept for 7 days
2. **Standard Logs**: Kept for 3 days
3. **Debug Logs**: Kept for 12 hours

### Regular Maintenance Tasks

1. **Update Knowledge Base**: Regularly update documents as information changes
2. **Monitor Costs**: Check AWS Cost Explorer to monitor usage costs
3. **Review Logs**: Periodically review logs for errors or issues
4. **Test Performance**: Run the test script to verify system performance

## Troubleshooting

### Common Issues

#### Chatbot Not Responding

1. Check that the API key is valid
2. Verify that the Lambda function is running correctly
3. Check CloudWatch Logs for errors

#### Slow Responses

1. Consider enabling provisioned concurrency
2. Check database performance metrics
3. Optimize document chunking

#### WebSocket Connection Issues

1. Check browser console for WebSocket errors
2. Verify that the WebSocket API is deployed correctly
3. Try manually reconnecting with `SmallBizChatbot.reconnectWebSocket()`

#### Document Processing Failures

1. Check that the document format is supported
2. Verify that the document is not too large
3. Check CloudWatch Logs for document processing errors

### Getting Support

If you encounter issues:

1. Check the troubleshooting guide in `docs/troubleshooting.md`
2. Review AWS service documentation
3. Open an issue on GitHub

## FAQ

### General Questions

**Q: How much does this solution cost to run?**
A: The base cost is approximately $15-20/month, with additional costs based on usage.

**Q: Which AWS regions are supported?**
A: Any region where Amazon Bedrock is available.

**Q: Can I use my own domain name?**
A: Yes, you can set up a custom domain in API Gateway and CloudFront.

### Technical Questions

**Q: How are documents processed?**
A: Documents are processed using Amazon Textract, split into semantic chunks, and stored as vector embeddings.

**Q: How does the chatbot know which information to retrieve?**
A: The system uses vector similarity search to find the most relevant document chunks.

**Q: Can I customize the AI model?**
A: Yes, you can change the Bedrock model in the configuration file.

**Q: How secure is the solution?**
A: The solution includes API key authentication, WAF protection, and encrypted storage.
