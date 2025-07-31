# **S3 Vector Utils - Two Version Architecture**

## **⚠️ Important Notice**

This project maintains **TWO DIFFERENT VERSIONS** of `s3_vector_utils.py`:

1. **`lambda_function/s3_vector_utils.py`** - Production Lambda version (2,289 lines)
2. **`src/backend/s3_vector_utils.py`** - Streamlined development/script version (542 lines)

## **🚨 DO NOT SYNC THESE FILES**

The `sync_lambda_files.py` script **intentionally excludes** `s3_vector_utils.py` because:
- The Lambda version has performance optimizations for production
- The backend version is streamlined for development scripts
- Syncing would break production functionality

## **📖 Full Documentation**

For complete details, see: **[docs/s3-vector-utils-versions.md](docs/s3-vector-utils-versions.md)**

## **🎯 Quick Reference**

### **Use Lambda Version For**:
- Production Lambda deployment
- High-performance vector searches
- Full caching and optimization features

### **Use Backend Version For**:
- Development scripts (`process_documents_locally.py`, `cleanup_vectors.py`)
- Local testing and debugging
- Administrative tasks (streamlined for clarity)

## **🔧 Maintenance**

When modifying vector utilities:
1. **Determine which version needs changes**
2. **Apply changes to appropriate version(s)**
3. **Test in target environment**
4. **Update documentation if needed**

**Never blindly sync these files between directories!**
