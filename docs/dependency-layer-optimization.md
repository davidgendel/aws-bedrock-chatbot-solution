# **Dependency Layer Optimization Analysis**

## **📋 Current State Analysis**

### **Current ChatbotDependenciesLayer Contents**:
```
numpy==1.26.4           # ~15MB - Used in lambda_function/s3_vector_utils.py
structlog==24.4.0       # ~1MB  - Used in lambda_function/logging_config.py
cachetools>=5.3.0       # ~50KB - Used in multiple lambda_function files
PyPDF2>=3.0.1          # ~2MB  - NOT used in lambda_function
python-docx>=1.1.0     # ~1MB  - NOT used in lambda_function
Pillow>=10.1.0         # ~8MB  - NOT used in lambda_function
textstat>=0.7.3        # ~100KB - NOT used in lambda_function
orjson>=3.9.0          # ~1MB  - NOT used in lambda_function
cryptography>=41.0.0   # ~5MB  - NOT used in lambda_function
python-dotenv>=1.0.0   # ~20KB - NOT used in lambda_function
```

**Total Layer Size**: ~33MB
**Actually Used in Lambda**: ~16MB (numpy, structlog, cachetools)
**Wasted Space**: ~17MB (52% waste!)

---

## **🎯 Usage Analysis**

### **✅ KEEP in ChatbotDependenciesLayer (Lambda Function Usage)**:

#### **1. numpy (15MB) - KEEP ✅**
**Usage**: `lambda_function/s3_vector_utils.py`
```python
import numpy as np
# Used for vector similarity calculations
```
**Justification**: Core functionality for vector operations

#### **2. structlog (1MB) - KEEP ✅**
**Usage**: `lambda_function/logging_config.py`
```python
import structlog
# Used for structured logging throughout Lambda
```
**Justification**: Essential for Lambda logging

#### **3. cachetools (50KB) - KEEP ✅**
**Usage**: Multiple files
```python
from cachetools import TTLCache, LRUCache
# Used in: cache_manager.py, bedrock_utils.py, s3_vector_utils.py
```
**Justification**: Core caching functionality

---

### **❌ REMOVE from ChatbotDependenciesLayer (Not Used in Lambda)**:

#### **4. PyPDF2 (2MB) - REMOVE ❌**
**Usage**: Only in `scripts/process_documents_locally.py`
```python
import PyPDF2  # Only used in local scripts
```
**Justification**: Document processing happens locally, not in Lambda

#### **5. python-docx (1MB) - REMOVE ❌**
**Usage**: Only in `scripts/process_documents_locally.py`
```python
from docx import Document  # Only used in local scripts
```
**Justification**: Document processing happens locally, not in Lambda

#### **6. Pillow (8MB) - REMOVE ❌**
**Usage**: Only in `scripts/process_documents_locally.py`
```python
from PIL import Image  # Only used in local scripts
```
**Justification**: Image processing happens locally, not in Lambda

#### **7. textstat (100KB) - REMOVE ❌**
**Usage**: Only in `scripts/process_documents_locally.py`
```python
import textstat  # Only used in local scripts
```
**Justification**: Text analysis happens locally, not in Lambda

#### **8. orjson (1MB) - REMOVE ❌**
**Usage**: Not found in any Lambda function files
**Justification**: Not used in Lambda functions

#### **9. cryptography (5MB) - REMOVE ❌**
**Usage**: Not found in Lambda function files
**Justification**: Not used in Lambda functions (boto3 handles AWS crypto)

#### **10. python-dotenv (20KB) - REMOVE ❌**
**Usage**: Not found in Lambda function files
**Justification**: Lambda uses environment variables directly

---

## **🔍 Additional Dependencies to Consider Adding**

### **Potential Additions**:

#### **1. scipy - INVESTIGATE 🔍**
**Current Status**: Available on system but not in requirements
**Usage**: `scripts/process_documents_locally.py` uses `scipy.spatial.distance.cosine`
**Size**: ~30MB
**Recommendation**: **DON'T ADD** - only used in scripts, not Lambda

#### **2. requests - CONSIDER 💭**
**Usage**: May be used for HTTP calls in Lambda
**Size**: ~500KB
**Check**: Need to verify if Lambda functions make HTTP requests

#### **3. urllib3 - ALREADY COVERED ✅**
**Status**: Included with boto3 layer
**Usage**: HTTP client functionality

---

## **📊 Recommended Layer Optimization**

### **Optimized ChatbotDependenciesLayer**:
```
# KEEP - Used in Lambda functions
numpy==1.26.4           # ~15MB - Vector operations
structlog==24.4.0       # ~1MB  - Structured logging  
cachetools>=5.3.0       # ~50KB - Caching functionality

# REMOVE - Only used in local scripts
# PyPDF2>=3.0.1          # Document processing (local only)
# python-docx>=1.1.0     # Document processing (local only)
# Pillow>=10.1.0         # Image processing (local only)
# textstat>=0.7.3        # Text analysis (local only)
# orjson>=3.9.0          # Not used anywhere in Lambda
# cryptography>=41.0.0   # Not needed (boto3 handles crypto)
# python-dotenv>=1.0.0   # Not needed (Lambda env vars)
```

**New Layer Size**: ~16MB (52% reduction!)
**Savings**: ~17MB per deployment

---

## **🏗️ Alternative Architecture Options**

### **Option A: Single Optimized Layer (Recommended)**
```
ChatbotDependenciesLayer:
- numpy==1.26.4
- structlog==24.4.0  
- cachetools>=5.3.0
```
**Benefits**: Simple, focused, minimal size

### **Option B: Split into Specialized Layers**
```
CoreLayer:
- structlog==24.4.0
- cachetools>=5.3.0

MathLayer:
- numpy==1.26.4

DocumentProcessingLayer (for scripts only):
- PyPDF2>=3.0.1
- python-docx>=1.1.0
- Pillow>=10.1.0
- textstat>=0.7.3
```
**Benefits**: More granular control
**Drawbacks**: More complexity

### **Option C: Local Script Requirements**
Create separate `scripts/requirements.txt`:
```
# For local document processing scripts
PyPDF2>=3.0.1
python-docx>=1.1.0
Pillow>=10.1.0
textstat>=0.7.3
orjson>=3.9.0
cryptography>=41.0.0
python-dotenv>=1.0.0
scipy>=1.9.0
```

---

## **🎯 Implementation Plan**

### **Phase 1: Remove Unused Dependencies**
1. **Update `lambda_layer/requirements.txt`**:
```diff
numpy==1.26.4
structlog==24.4.0
cachetools>=5.3.0
- PyPDF2>=3.0.1
- python-docx>=1.1.0
- Pillow>=10.1.0
- textstat>=0.7.3
- orjson>=3.9.0
- cryptography>=41.0.0
- python-dotenv>=1.0.0
```

2. **Create `scripts/requirements.txt`**:
```
PyPDF2>=3.0.1
python-docx>=1.1.0
Pillow>=10.1.0
textstat>=0.7.3
orjson>=3.9.0
cryptography>=41.0.0
python-dotenv>=1.0.0
scipy>=1.9.0
```

3. **Update script installation instructions**:
```bash
# For running scripts locally
pip install -r scripts/requirements.txt
```

### **Phase 2: Test and Validate**
1. **Test Lambda deployment** with reduced layer
2. **Verify script functionality** with separate requirements
3. **Monitor cold start performance** improvements

---

## **📈 Expected Benefits**

### **Performance Improvements**:
- **52% smaller layer** (33MB → 16MB)
- **Faster cold starts** (less code to load)
- **Faster deployments** (smaller packages)

### **Cost Savings**:
- **Reduced storage costs** (smaller layers)
- **Faster Lambda initialization**
- **Lower data transfer costs**

### **Operational Benefits**:
- **Clearer separation** of concerns
- **Easier maintenance** (fewer dependencies)
- **Reduced security surface** (fewer packages to monitor)

---

## **🔍 Verification Steps**

### **Before Changes**:
```bash
# Check current layer size
aws lambda get-layer-version --layer-name ChatbotDependenciesLayer --version-number X

# Test Lambda function
aws lambda invoke --function-name ChatbotFunction test-output.json
```

### **After Changes**:
```bash
# Verify reduced layer size
aws lambda get-layer-version --layer-name ChatbotDependenciesLayer --version-number Y

# Test Lambda function still works
aws lambda invoke --function-name ChatbotFunction test-output.json

# Test scripts still work locally
cd scripts && python process_documents_locally.py --help
```

---

## **⚠️ Risks and Mitigations**

### **Risk 1: Missing Dependencies**
**Mitigation**: Thorough testing of Lambda functions after changes

### **Risk 2: Script Failures**
**Mitigation**: Create separate `scripts/requirements.txt` and update documentation

### **Risk 3: Future Dependency Needs**
**Mitigation**: Document the separation clearly and provide easy way to add back if needed

---

## **📝 Recommendation**

**IMMEDIATE ACTION**: Remove unused dependencies from ChatbotDependenciesLayer

**Benefits**:
- 52% size reduction (17MB savings)
- Faster cold starts
- Clearer architecture
- Lower costs

**Implementation**:
1. Update `lambda_layer/requirements.txt` (remove 7 unused packages)
2. Create `scripts/requirements.txt` (for local processing)
3. Test deployment
4. Update documentation

This optimization will significantly improve Lambda performance while maintaining all functionality.
