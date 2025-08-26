# 🔧 Vector Index Management Guide

This guide covers how to manage your AWS S3 Vector indexes for the RAG chatbot solution.

## 🚀 Quick Start

### Option 1: Use the Wrapper Script (Recommended)

The easiest way to manage vector indexes is using the wrapper script that automatically handles environment variables:

```bash
# List all vector indexes
./vector_manager.sh list

# Get detailed information about an index
./vector_manager.sh info chatbot-document-vectors

# Optimize vector index performance
./vector_manager.sh optimize chatbot-document-vectors

# Show comprehensive statistics
./vector_manager.sh stats

# Clear all vector caches
./vector_manager.sh clear-cache
```

### Option 2: Direct Commands

If you prefer to use the Python script directly, first set up the environment:

```bash
# Set up environment variables
source setup_vector_env.sh

# Then run commands directly
python3 scripts/manage_vector_indexes.py optimize chatbot-document-vectors
python3 scripts/manage_vector_indexes.py list
python3 scripts/manage_vector_indexes.py stats
```

## 📋 Available Commands

| Command | Description | Usage |
|---------|-------------|-------|
| **list** | List all vector indexes with details | `./vector_manager.sh list` |
| **info** | Show detailed index information | `./vector_manager.sh info <index-name>` |
| **optimize** | Optimize vector index performance | `./vector_manager.sh optimize <index-name>` |
| **stats** | Show comprehensive statistics | `./vector_manager.sh stats` |
| **clear-cache** | Clear all vector caches | `./vector_manager.sh clear-cache` |
| **create** | Create a new vector index | `./vector_manager.sh create <index-name>` |
| **delete** | Delete a vector index | `./vector_manager.sh delete <index-name>` |

## 🔍 Command Details

### List Command
```bash
./vector_manager.sh list
```
**Output:**
- ✅ Index status and name
- 🆔 Index ARN/ID
- 📊 Dimensions (1024 for Nova Lite)
- 🎯 Similarity metric (cosine)
- 📅 Creation timestamp
- 🔢 Vector count (when available)

### Info Command
```bash
./vector_manager.sh info chatbot-document-vectors
```
**Output:**
- 📋 Detailed index configuration
- 📊 Statistics and metrics
- 🕒 Creation and update timestamps
- 🔧 API type and status

### Optimize Command
```bash
./vector_manager.sh optimize chatbot-document-vectors
```
**What it does:**
- 🧹 Clears all vector caches for fresh data
- 📊 Validates index exists and is accessible
- ⚡ Triggers S3 Vectors maintenance operations
- 📈 Returns optimization results and statistics

### Stats Command
```bash
./vector_manager.sh stats
```
**Output:**
- 🌐 Overall statistics across all indexes
- 💰 Estimated monthly costs
- 💾 Cache performance metrics
- 📋 Individual index details

## 🛠️ Troubleshooting

### Common Issues

#### 1. Environment Variable Not Set
**Error:** `VECTOR_BUCKET_NAME environment variable not set`

**Solution:**
```bash
# Use the wrapper script (automatically sets variables)
./vector_manager.sh optimize chatbot-document-vectors

# OR set up environment manually
source setup_vector_env.sh
python3 scripts/manage_vector_indexes.py optimize chatbot-document-vectors
```

#### 2. Wrong Command Syntax
**Error:** `unrecognized arguments: --optimize`

**Correct Usage:**
```bash
# ❌ Wrong
python3 scripts/manage_vector_indexes.py --optimize

# ✅ Correct
python3 scripts/manage_vector_indexes.py optimize chatbot-document-vectors
# OR
./vector_manager.sh optimize chatbot-document-vectors
```

#### 3. Index Not Found
**Error:** `Index 'chatbot-document-vectors' not found`

**Solution:**
```bash
# Check what indexes exist
./vector_manager.sh list

# Verify deployment status
./deploy.sh status
```

#### 4. Permission Issues
**Error:** `AccessDenied` or similar AWS errors

**Solution:**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify IAM permissions for S3 Vectors service
aws iam get-role --role-name <your-lambda-role>
```

## 📊 Understanding the Output

### Index Status Indicators
- ✅ **ACTIVE**: Index is ready and operational
- ⚠️ **UNKNOWN**: Status could not be determined
- ❌ **ERROR**: Index has issues

### Cache Statistics
- **Size**: Current cache entries / Maximum capacity
- **Hit Rate**: Percentage of cache hits (higher is better)
- **Types**: Similarity, Metadata, and Embedding caches

### Cost Estimates
- **Storage Cost**: Based on vector storage size
- **Query Cost**: Per 1,000 vector queries
- **Data Processing**: Per TB of vector data processed

## 🔧 Advanced Usage

### Creating Custom Indexes
```bash
# Create a new index with default settings
./vector_manager.sh create my-custom-index

# The script will use standard settings:
# - Dimensions: 1536 (for Titan embeddings) or 1024 (for Nova)
# - Similarity: cosine
# - Data Type: float32
```

### Batch Operations
```bash
# Get stats for all indexes
./vector_manager.sh stats

# Clear all caches
./vector_manager.sh clear-cache

# List all indexes
./vector_manager.sh list
```

### Monitoring and Maintenance
```bash
# Regular optimization (recommended weekly)
./vector_manager.sh optimize chatbot-document-vectors

# Monitor cache performance
./vector_manager.sh stats | grep "Hit Rate"

# Check index health
./vector_manager.sh info chatbot-document-vectors
```

## 🔐 Security Notes

- Environment variables are automatically sourced from CloudFormation
- AWS credentials are handled by IAM roles (no hardcoded keys)
- All operations use AWS SDK with proper authentication
- Vector data is encrypted at rest in S3

## 📈 Performance Tips

1. **Regular Optimization**: Run optimize weekly for best performance
2. **Cache Monitoring**: Check hit rates in stats output
3. **Index Maintenance**: Monitor vector counts and storage usage
4. **Cost Optimization**: Use stats to track monthly cost estimates

## 🆘 Getting Help

If you encounter issues:

1. **Check the logs**: Look for error messages in the command output
2. **Verify deployment**: Run `./deploy.sh status`
3. **Check permissions**: Ensure proper AWS IAM roles
4. **Review configuration**: Verify environment variables are set correctly

## 📚 Related Documentation

- [Main README](README.md) - Overall project documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [docs/troubleshooting.md](docs/troubleshooting.md) - General troubleshooting

---

**🎯 Ready to optimize your vectors?**
```bash
./vector_manager.sh optimize chatbot-document-vectors
```
