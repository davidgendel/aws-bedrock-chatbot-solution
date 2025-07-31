# **Requirements Files Guide**

## **📋 Overview**

This project has multiple requirements files for different purposes. Here's when to use each:

## **🎯 Requirements Files Explained**

### **For Deployment (Automatic - No Action Needed)**

#### **`lambda_layer/requirements.txt`**
- **Purpose**: Lambda layer dependencies (automatic)
- **Usage**: Handled automatically by `./deploy.sh`
- **Contents**: numpy, structlog, cachetools
- **Action**: ❌ **DO NOT install manually**

#### **`layers/boto3-layer/`**
- **Purpose**: boto3 layer (automatic)
- **Usage**: Handled automatically by `./deploy.sh`
- **Contents**: boto3, botocore, s3transfer
- **Action**: ❌ **DO NOT install manually**

### **For Local Usage (Manual Installation)**

#### **`scripts/requirements.txt`** ✅ **RECOMMENDED**
- **Purpose**: Local document processing scripts
- **Usage**: `pip install -r scripts/requirements.txt`
- **When**: Only if you want to run local document processing
- **Contents**: PyPDF2, python-docx, Pillow, textstat, etc.

#### **`requirements-dev.txt`**
- **Purpose**: Development and testing
- **Usage**: `pip install -r requirements-dev.txt`
- **When**: Only for developers working on the codebase
- **Contents**: pytest, moto, fastapi, etc.

### **For Reference Only**

#### **`requirements.txt`**
- **Purpose**: Main project dependencies (reference)
- **Usage**: ❌ **DO NOT install manually**
- **When**: Used by CDK/deploy.sh internally
- **Contents**: boto3, CDK, numpy, scipy, etc.

#### **`requirements-local.txt`**
- **Purpose**: Local development (reference)
- **Usage**: ❌ **DO NOT install manually**
- **When**: Alternative to requirements.txt
- **Contents**: Similar to requirements.txt

## **🚀 Quick Start Guide**

### **For Normal Users (Just Deploy)**
```bash
# Deploy the chatbot (no pip install needed)
./deploy.sh deploy
```

### **For Document Processing (Local Scripts)**
```bash
# Install script dependencies
pip install -r scripts/requirements.txt

# Process documents locally
python3 scripts/process_documents_locally.py --folder ./documents
```

### **For Developers**
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python3 run_tests.py
```

## **❌ Common Mistakes to Avoid**

1. **DON'T** run `pip install -r requirements.txt` (not needed for deployment)
2. **DON'T** run `pip install -r lambda_layer/requirements.txt` (automatic)
3. **DON'T** install dependencies before deployment (deploy.sh handles it)

## **✅ Correct Usage Summary**

| Task | Command | When |
|------|---------|------|
| **Deploy chatbot** | `./deploy.sh deploy` | Always |
| **Process documents locally** | `pip install -r scripts/requirements.txt` | Optional |
| **Develop/test code** | `pip install -r requirements-dev.txt` | Developers only |
| **Check status** | `./deploy.sh status` | After deployment |

## **🔍 Troubleshooting**

**Q: Should I install requirements.txt?**
A: No, `./deploy.sh` handles all deployment dependencies automatically.

**Q: I want to process documents locally, what do I install?**
A: `pip install -r scripts/requirements.txt`

**Q: I'm getting import errors during deployment**
A: Don't install anything manually. Run `./deploy.sh deploy` - it handles all dependencies.

**Q: Which Python version?**
A: Python 3.9+ required. Lambda uses Python 3.12.
