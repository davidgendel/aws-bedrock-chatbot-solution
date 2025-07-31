# **Documentation Cleanup Plan - IDENTIFIED ISSUES**

## **🚨 CRITICAL ISSUES FOUND**

### **1. DUPLICATE DIRECTORIES**
**Problem**: Two identical documentation directories exist:
- `docs/` (13 files)
- `documents/` (6 files)

**Duplicated Files** (100% identical content):
- `cost-analysis.md`
- `deployment-guide.md` 
- `pricing.md`
- `uninstall-guide.md`
- `user-guide.md`

### **2. INCONSISTENT REQUIREMENTS INSTRUCTIONS**
**Problem**: Multiple requirements files with confusing instructions:

| File | Purpose | Current Instructions |
|------|---------|---------------------|
| `requirements.txt` | Main project deps | Used in some docs |
| `requirements-local.txt` | Local development | Used in documents/README.md |
| `requirements-dev.txt` | Development/testing | Used in some docs |
| `lambda_layer/requirements.txt` | Lambda layer (auto) | Not for manual install |
| `scripts/requirements.txt` | Local scripts only | Correct usage in README.md |

### **3. INCORRECT CDK DEPLOY REFERENCE**
**Problem**: One file references `cdk deploy` instead of `./deploy.sh deploy`:
- `docs/dependency-removal-implementation-plan.md`

### **4. CONFUSING REQUIREMENTS GUIDANCE**
**Problem**: Different docs tell users to install different requirements files:
- Some say `pip install -r requirements.txt`
- Some say `pip install -r requirements-local.txt`
- Some say `pip install -r scripts/requirements.txt`

---

## **🎯 CLEANUP ACTIONS**

### **Action 1: Remove Duplicate Directory**
**Decision**: Keep `docs/` directory, remove `documents/` directory
**Reason**: `docs/` has more comprehensive documentation

### **Action 2: Fix Deployment Instructions**
**Fix**: Change `cdk deploy` to `./deploy.sh deploy` in dependency plan

### **Action 3: Clarify Requirements Usage**
**Create clear guidance**:
- **For deployment**: No manual pip install needed (deploy.sh handles it)
- **For local scripts**: `pip install -r scripts/requirements.txt`
- **For development**: `pip install -r requirements-dev.txt`

### **Action 4: Update Main README**
**Ensure README.md has clear, consistent instructions**

---

## **📋 IMPLEMENTATION CHECKLIST**

- [ ] Remove `documents/` directory (duplicates)
- [ ] Fix `cdk deploy` reference in dependency plan
- [ ] Update all documentation with consistent requirements instructions
- [ ] Verify README.md has correct guidance
- [ ] Remove confusing references to multiple requirements files
