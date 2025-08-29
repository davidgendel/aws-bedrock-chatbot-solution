# **Requirements Files Guide**

## **📋 Overview**

This project automatically manages all dependencies using virtual environments. No manual `pip install` required for normal usage.

## **🎯 Requirements Files Explained**

### **For Deployment (Automatic - No Action Needed)**

#### **`requirements.txt`**
- **Purpose**: Main deployment dependencies (automatic)
- **Usage**: Handled automatically by `./chatbot`
- **Contents**: boto3, CDK, numpy, scipy, etc.
- **Action**: ❌ **DO NOT install manually**

#### **`lambda_layer/requirements.txt`**
- **Purpose**: Lambda layer dependencies (automatic)
- **Usage**: Handled automatically by `./chatbot`
- **Contents**: numpy, structlog, cachetools
- **Action**: ❌ **DO NOT install manually**

### **For Document Processing (Automatic - No Action Needed)**

#### **`scripts/requirements.txt`**
- **Purpose**: Document processing dependencies (automatic)
- **Usage**: Handled automatically by `./process_documents`
- **Contents**: PyPDF2, python-docx, Pillow, textstat, etc.
- **Action**: ❌ **DO NOT install manually**

### **For Development Only**

#### **`requirements-dev.txt`**
- **Purpose**: Development and testing
- **Usage**: `pip install -r requirements-dev.txt`
- **When**: Only for developers working on the codebase
- **Contents**: pytest, moto, fastapi, etc.

## **🚀 Quick Start Guide**

### **For Normal Users**
```bash
# Deploy the chatbot (dependencies handled automatically)
./chatbot deploy

# Process documents (dependencies handled automatically)
./process_documents --folder ./documents
```

### **For Developers**
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python3 run_tests.py
```

## **🔧 Virtual Environment Management**

The project automatically creates and manages virtual environments:
- `.venv` - For deployment and CLI operations
- `.venv-scripts` - For document processing

**Prerequisites**: Ensure `python3-venv` is installed:
```bash
# Ubuntu/Debian
sudo apt install python3-venv

# RHEL/CentOS
sudo yum install python3-venv
```

## **❌ Common Mistakes to Avoid**

1. **DON'T** run `pip install -r requirements.txt` (handled automatically)
2. **DON'T** run `pip install -r scripts/requirements.txt` (handled automatically)
3. **DON'T** create virtual environments manually (handled automatically)

## **✅ Correct Usage Summary**

| Task | Command | Dependencies |
|------|---------|--------------|
| **Deploy chatbot** | `./chatbot deploy` | Automatic |
| **Process documents** | `./process_documents --folder ./docs` | Automatic |
| **Develop/test code** | `pip install -r requirements-dev.txt` | Manual |
| **Check status** | `./chatbot status` | Automatic |

## **🔍 Troubleshooting**

**Q: Should I install requirements.txt?**
A: No, `./chatbot` handles all dependencies automatically using virtual environments.

**Q: I want to process documents locally, what do I install?**
A: Nothing. Use `./process_documents` - it handles dependencies automatically.

**Q: I'm getting "python3-venv not found" errors**
A: Install python3-venv package: `sudo apt install python3-venv` (Ubuntu/Debian)

**Q: Which Python version?**
A: Python 3.12+ required. Lambda uses Python 3.12.
