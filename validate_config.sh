#!/bin/bash
#
# Configuration Validation Script
# 
# This script validates the deployment environment and configuration
# before attempting deployment.
#

set -e

# Colors for output
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                    RAG Chatbot Configuration Validator                       ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo

# Source validation library if available
if [ -f "scripts/common/validation.sh" ]; then
    source scripts/common/validation.sh
    
    echo -e "${CYAN}🚀 Running comprehensive validation...${NC}"
    echo
    
    if validate_deployment_environment; then
        echo
        echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║ ✅ All validations passed! Your environment is ready for deployment.        ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
        echo
        echo -e "${CYAN}🚀 Ready to deploy? Run:${NC}"
        echo -e "   ${BOLD}./deploy.sh deploy${NC}"
        echo
        exit 0
    else
        echo
        echo -e "${RED}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║ ❌ Validation failed! Please fix the issues above before deploying.         ║${NC}"
        echo -e "${RED}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
        echo
        exit 1
    fi
else
    # Fallback validation if library not available
    echo -e "${YELLOW}⚠️  Validation library not found, running basic checks...${NC}"
    echo
    
    validation_failed=false
    
    # Check AWS CLI
    echo -e "${CYAN}🔍 Checking AWS CLI...${NC}"
    if command -v aws &> /dev/null; then
        echo -e "${GREEN}✅ AWS CLI found${NC}"
    else
        echo -e "${RED}❌ AWS CLI not found${NC}"
        echo -e "${YELLOW}💡 Install from: https://aws.amazon.com/cli/${NC}"
        validation_failed=true
    fi
    
    # Check AWS credentials
    echo -e "${CYAN}🔑 Checking AWS credentials...${NC}"
    if aws sts get-caller-identity &> /dev/null; then
        account_id=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
        echo -e "${GREEN}✅ AWS credentials valid (Account: $account_id)${NC}"
    else
        echo -e "${RED}❌ AWS credentials not configured or invalid${NC}"
        echo -e "${YELLOW}💡 Run: aws configure${NC}"
        validation_failed=true
    fi
    
    # Check region
    echo -e "${CYAN}🌍 Checking AWS region...${NC}"
    region=$(aws configure get region 2>/dev/null || echo "")
    if [ -n "$region" ]; then
        echo -e "${GREEN}✅ AWS region configured: $region${NC}"
    else
        echo -e "${YELLOW}⚠️  No region configured, will use us-east-1${NC}"
        echo -e "${YELLOW}💡 Set region: aws configure set region <your-region>${NC}"
    fi
    
    # Check Python
    echo -e "${CYAN}🐍 Checking Python...${NC}"
    if command -v python3 &> /dev/null; then
        python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
        echo -e "${GREEN}✅ Python $python_version found${NC}"
    else
        echo -e "${RED}❌ Python 3 not found${NC}"
        echo -e "${YELLOW}💡 Install from: https://python.org/downloads/${NC}"
        validation_failed=true
    fi
    
    # Check Node.js
    echo -e "${CYAN}📦 Checking Node.js...${NC}"
    if command -v node &> /dev/null; then
        node_version=$(node --version 2>/dev/null)
        echo -e "${GREEN}✅ Node.js $node_version found${NC}"
    else
        echo -e "${RED}❌ Node.js not found${NC}"
        echo -e "${YELLOW}💡 Install from: https://nodejs.org/${NC}"
        validation_failed=true
    fi
    
    # Check config.json
    echo -e "${CYAN}📋 Checking configuration file...${NC}"
    if [ -f "config.json" ]; then
        if python3 -c "import json; json.load(open('config.json'))" 2>/dev/null; then
            echo -e "${GREEN}✅ config.json is valid${NC}"
        else
            echo -e "${RED}❌ config.json has invalid JSON${NC}"
            validation_failed=true
        fi
    else
        echo -e "${RED}❌ config.json not found${NC}"
        validation_failed=true
    fi
    
    echo
    
    if [ "$validation_failed" = false ]; then
        echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║ ✅ Basic validation passed! Your environment looks ready for deployment.    ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
        echo
        echo -e "${CYAN}🚀 Ready to deploy? Run:${NC}"
        echo -e "   ${BOLD}./deploy.sh deploy${NC}"
        echo
        exit 0
    else
        echo -e "${RED}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║ ❌ Validation failed! Please fix the issues above before deploying.         ║${NC}"
        echo -e "${RED}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
        echo
        exit 1
    fi
fi
