#!/bin/bash
#
# Common Validation Library
# 
# This library provides validation functions for deployment prerequisites,
# configuration files, and system dependencies.
#

# Source AWS configuration library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/aws_config.sh"

# Colors for output (only define if not already defined)
if [ -z "${GREEN:-}" ]; then
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly RED='\033[0;31m'
    readonly CYAN='\033[0;36m'
    readonly NC='\033[0m'
fi

#
# Validate system prerequisites
#
validate_system_prerequisites() {
    echo -e "${CYAN}🔍 Checking system prerequisites...${NC}"
    
    local missing_deps=()
    local warnings=()
    
    # Required commands
    local required_commands=("aws" "python3" "git")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    # Optional but recommended commands
    local optional_commands=("jq" "docker" "node" "npm")
    for cmd in "${optional_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            warnings+=("$cmd (optional but recommended)")
        fi
    done
    
    # Report missing dependencies
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${RED}❌ Missing required dependencies:${NC}"
        for dep in "${missing_deps[@]}"; do
            echo -e "   • $dep"
        done
        echo -e "${YELLOW}💡 Installation suggestions:${NC}"
        echo -e "   • AWS CLI: https://aws.amazon.com/cli/"
        echo -e "   • Python 3: https://python.org/downloads/"
        echo -e "   • Git: https://git-scm.com/downloads"
        return 1
    fi
    
    # Report warnings
    if [ ${#warnings[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Optional dependencies not found:${NC}"
        for warning in "${warnings[@]}"; do
            echo -e "   • $warning"
        done
    fi
    
    echo -e "${GREEN}✅ System prerequisites satisfied${NC}"
    return 0
}

#
# Validate Python environment
#
validate_python_environment() {
    echo -e "${CYAN}🐍 Validating Python environment...${NC}"
    
    # Check Python version
    if command -v python3 &> /dev/null; then
        local python_version
        python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
        local major minor
        major=$(echo "$python_version" | cut -d. -f1)
        minor=$(echo "$python_version" | cut -d. -f2)
        
        if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 9 ]); then
            echo -e "${RED}❌ Python version $python_version is too old (need 3.9+)${NC}"
            return 1
        fi
        
        echo -e "${GREEN}✅ Python $python_version${NC}"
    else
        echo -e "${RED}❌ Python 3 not found${NC}"
        return 1
    fi
    
    # Check pip
    if ! python3 -m pip --version &> /dev/null; then
        echo -e "${YELLOW}⚠️  pip not available${NC}"
        echo -e "${YELLOW}💡 Install pip: python3 -m ensurepip --upgrade${NC}"
    else
        echo -e "${GREEN}✅ pip available${NC}"
    fi
    
    return 0
}

#
# Validate configuration file
#
validate_config_file() {
    local config_file="${1:-config.json}"
    
    echo -e "${CYAN}📋 Validating configuration file: $config_file${NC}"
    
    # Check if file exists
    if [ ! -f "$config_file" ]; then
        echo -e "${RED}❌ Configuration file not found: $config_file${NC}"
        return 1
    fi
    
    # Check if it's valid JSON
    if command -v jq &> /dev/null; then
        if ! jq empty "$config_file" 2>/dev/null; then
            echo -e "${RED}❌ Invalid JSON in configuration file${NC}"
            return 1
        fi
    else
        # Basic JSON validation without jq
        if ! python3 -c "import json; json.load(open('$config_file'))" 2>/dev/null; then
            echo -e "${RED}❌ Invalid JSON in configuration file${NC}"
            return 1
        fi
    fi
    
    echo -e "${GREEN}✅ Configuration file is valid${NC}"
    return 0
}

#
# Validate AWS permissions
#
validate_aws_permissions() {
    echo -e "${CYAN}🔐 Validating AWS permissions...${NC}"
    
    # Test basic AWS operations
    local tests=(
        "aws sts get-caller-identity"
        "aws s3 ls"
        "aws cloudformation list-stacks --max-items 1"
    )
    
    local failed_tests=()
    
    for test in "${tests[@]}"; do
        if ! $test &> /dev/null; then
            failed_tests+=("$test")
        fi
    done
    
    if [ ${#failed_tests[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Some AWS operations failed (may indicate insufficient permissions):${NC}"
        for failed_test in "${failed_tests[@]}"; do
            echo -e "   • $failed_test"
        done
        echo -e "${YELLOW}💡 Ensure your AWS user has appropriate permissions for deployment${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Basic AWS permissions validated${NC}"
    return 0
}

#
# Validate deployment environment
#
validate_deployment_environment() {
    echo -e "${CYAN}🚀 Validating deployment environment...${NC}"
    
    local validation_failed=false
    
    # Run all validations
    if ! validate_system_prerequisites; then
        validation_failed=true
    fi
    
    if ! validate_python_environment; then
        validation_failed=true
    fi
    
    if ! validate_aws_environment; then
        validation_failed=true
    fi
    
    if ! validate_config_file; then
        validation_failed=true
    fi
    
    if ! validate_aws_permissions; then
        validation_failed=true
    fi
    
    if [ "$validation_failed" = true ]; then
        echo -e "${RED}❌ Deployment environment validation failed${NC}"
        echo -e "${YELLOW}💡 Please fix the issues above before proceeding${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Deployment environment validation passed${NC}"
    return 0
}

#
# Validate CloudFormation stack exists
#
validate_stack_exists() {
    local stack_name="${1:-ChatbotRagStack}"
    
    if aws cloudformation describe-stacks --stack-name "$stack_name" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

#
# Get stack outputs safely
#
get_stack_output() {
    local stack_name="$1"
    local output_key="$2"
    
    if [ -z "$stack_name" ] || [ -z "$output_key" ]; then
        echo "ERROR: Stack name and output key required" >&2
        return 1
    fi
    
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text 2>/dev/null || echo ""
}

#
# Validate vector resources exist
#
validate_vector_resources() {
    local vector_bucket_name="$1"
    local vector_index_name="$2"
    
    if [ -z "$vector_bucket_name" ] || [ -z "$vector_index_name" ]; then
        echo -e "${YELLOW}⚠️  Vector resource names not provided for validation${NC}"
        return 1
    fi
    
    echo -e "${CYAN}🔍 Validating vector resources...${NC}"
    
    # Check if S3 Vectors service is available
    if ! aws s3vectors get-vector-bucket --vector-bucket-name "$vector_bucket_name" &> /dev/null; then
        echo -e "${YELLOW}⚠️  Vector bucket '$vector_bucket_name' not found or not accessible${NC}"
        return 1
    fi
    
    if ! aws s3vectors get-index --vector-bucket-name "$vector_bucket_name" --index-name "$vector_index_name" &> /dev/null; then
        echo -e "${YELLOW}⚠️  Vector index '$vector_index_name' not found or not accessible${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Vector resources validated${NC}"
    return 0
}
