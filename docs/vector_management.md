# 🔧 Vector Index Management Guide

This guide covers how to manage your AWS S3 Vector indexes for the RAG chatbot solution.

## 🚀 Quick Start

### Recommended Commands

The easiest way to manage vector indexes is using the chatbot CLI:

```bash
# List all vector indexes
./chatbot vector list

# Get detailed information about an index
./chatbot vector info

# Optimize vector index performance
./chatbot vector optimize

# Show comprehensive statistics
./chatbot vector stats

# Clear all vector caches
./chatbot vector clear-cache
```

### Direct Python Commands

If you prefer to use the Python script directly:

```bash
# Run commands directly (environment is handled automatically)
python3 scripts/manage_vector_indexes.py optimize
python3 scripts/manage_vector_indexes.py list
python3 scripts/manage_vector_indexes.py stats
```

## 📋 Available Commands

| Command | Description | Usage |
|---------|-------------|-------|
| **list** | List all vector indexes with details | `./chatbot vector list` |
| **info** | Show detailed index information | `./chatbot vector info` |
| **optimize** | Optimize vector index performance | `./chatbot vector optimize` |
| **stats** | Show comprehensive statistics | `./chatbot vector stats` |
| **clear-cache** | Clear all vector caches | `./chatbot vector clear-cache` |
| **create** | Create a new vector index | `./chatbot vector create <index-name>` |
| **delete** | Delete a vector index | `./chatbot vector delete <index-name>` |

## 🔍 Command Details

### List Command
```bash
./chatbot vector list
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
./chatbot vector info
```
**Output:**
- 📋 Detailed index configuration
- 📊 Statistics and metrics
- 🕒 Creation and update timestamps
- 🔧 API type and status

### Optimize Command
```bash
./chatbot vector optimize
```
**What it does:**
- 🧹 Clears all vector caches for fresh data
- 📊 Validates index exists and is accessible
- ⚡ Triggers S3 Vectors maintenance operations
- 📈 Returns optimization results and statistics

### Stats Command
```bash
./chatbot vector stats
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
./chatbot vector optimize

# OR run Python script directly (environment handled automatically)
python3 scripts/manage_vector_indexes.py optimize
```

#### 2. Wrong Command Syntax
**Error:** `unrecognized arguments: --optimize`

**Correct Usage:**
```bash
# ❌ Wrong
python3 scripts/manage_vector_indexes.py --optimize

# ✅ Correct
python3 scripts/manage_vector_indexes.py optimize
# OR
./chatbot vector optimize
```

#### 3. Index Not Found
**Error:** `Index 'chatbot-document-vectors' not found`

**Solution:**
```bash
# Check what indexes exist
./chatbot vector list

# Verify deployment status
./chatbot status
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
./chatbot vector create my-custom-index

# The script will use standard settings:
# - Dimensions: 1536 (for Titan embeddings) or 1024 (for Nova)
# - Similarity: cosine
# - Data Type: float32
```

### Batch Operations
```bash
# Get stats for all indexes
./chatbot vector stats

# Clear all caches
./chatbot vector clear-cache

# List all indexes
./chatbot vector list
```

### Monitoring and Maintenance
```bash
# Regular optimization (recommended weekly)
./chatbot vector optimize

# Monitor cache performance
./chatbot vector stats | grep "Hit Rate"

# Check index health
./chatbot vector info
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
2. **Verify deployment**: Run `./chatbot status`
3. **Check permissions**: Ensure proper AWS IAM roles
4. **Review configuration**: Verify environment variables are set correctly

## 📚 Related Documentation

- [Main README](README.md) - Overall project documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [docs/troubleshooting.md](docs/troubleshooting.md) - General troubleshooting

---

**🎯 Ready to optimize your vectors?**
```bash
./chatbot vector optimize
```
