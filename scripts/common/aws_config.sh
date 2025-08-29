#!/bin/bash
#
# Common AWS Configuration Detection Library
# 
# This library provides centralized functions for detecting AWS account ID and region
# across all deployment and management scripts.
#

# Colors for output (only define if not already defined)
if [ -z "${GREEN:-}" ]; then
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly RED='\033[0;31m'
    readonly CYAN='\033[0;36m'
    readonly NC='\033[0m'
fi

# Global variables for caching
_AWS_ACCOUNT_ID=""
_AWS_REGION=""

#
# Get AWS configuration (account ID or region)
#
# Usage: get_aws_config "account" or get_aws_config "region"
# Returns: The requested configuration value
# Exit codes: 0 = success, 1 = error
#
get_aws_config() {
    local config_type="$1"
    
    if [ -z "$config_type" ]; then
        echo "ERROR: Configuration type required (account|region)" >&2
        return 1
    fi
    
    case "$config_type" in
        "account")
            # Return cached value if available
            if [ -n "$_AWS_ACCOUNT_ID" ]; then
                echo "$_AWS_ACCOUNT_ID"
                return 0
            fi
            
            # Get account ID from AWS CLI
            local account_id
            account_id=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
            
            if [ $? -ne 0 ] || [ -z "$account_id" ] || [ "$account_id" = "None" ]; then
                echo "ERROR: Cannot determine AWS account ID." >&2
                echo "       Please ensure AWS CLI is configured with valid credentials." >&2
                echo "       Run: aws configure" >&2
                return 1
            fi
            
            # Cache and return
            _AWS_ACCOUNT_ID="$account_id"
            echo "$account_id"
            ;;
            
        "region")
            # Return cached value if available
            if [ -n "$_AWS_REGION" ]; then
                echo "$_AWS_REGION"
                return 0
            fi
            
            # Priority: ENV_VAR → AWS_CONFIG → CONFIG_JSON → ERROR
            local region=""
            
            # Try environment variables first
            region="${AWS_REGION:-${AWS_DEFAULT_REGION:-${CDK_DEPLOY_REGION:-}}}"
            
            # Try AWS CLI configuration
            if [ -z "$region" ]; then
                region=$(aws configure get region 2>/dev/null || echo "")
            fi
            
            # Try config.json file
            if [ -z "$region" ] && [ -f "config.json" ]; then
                if command -v jq &> /dev/null; then
                    region=$(jq -r '.region // empty' config.json 2>/dev/null || echo "")
                else
                    # Fallback without jq - simple grep/sed approach
                    region=$(grep -o '"region"[[:space:]]*:[[:space:]]*"[^"]*"' config.json 2>/dev/null | sed 's/.*"region"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || echo "")
                fi
            fi
            
            # Try parent directory config.json (for scripts in subdirectories)
            if [ -z "$region" ] && [ -f "../config.json" ]; then
                if command -v jq &> /dev/null; then
                    region=$(jq -r '.region // empty' ../config.json 2>/dev/null || echo "")
                else
                    region=$(grep -o '"region"[[:space:]]*:[[:space:]]*"[^"]*"' ../config.json 2>/dev/null | sed 's/.*"region"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || echo "")
                fi
            fi
            
            if [ -z "$region" ]; then
                echo "ERROR: Cannot determine AWS region." >&2
                echo "       Please set AWS_REGION environment variable or run 'aws configure'." >&2
                echo "       Alternatively, set 'region' in config.json file." >&2
                return 1
            fi
            
            # Cache and return
            _AWS_REGION="$region"
            echo "$region"
            ;;
            
        *)
            echo "ERROR: Invalid configuration type '$config_type'. Use 'account' or 'region'." >&2
            return 1
            ;;
    esac
}

#
# Validate AWS environment and export configuration
#
# This function performs comprehensive validation and exports environment variables
# for use by other scripts.
#
validate_aws_environment() {
    echo -e "${CYAN}🔍 Validating AWS environment...${NC}"
    
    # Check AWS CLI availability
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}❌ AWS CLI not found.${NC}"
        echo -e "${YELLOW}💡 Please install AWS CLI first:${NC}"
        echo -e "   • Visit: https://aws.amazon.com/cli/"
        echo -e "   • Or run: pip install awscli"
        return 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}❌ AWS credentials not configured or invalid.${NC}"
        echo -e "${YELLOW}💡 Please configure AWS credentials:${NC}"
        echo -e "   • Run: aws configure"
        echo -e "   • Or set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
        return 1
    fi
    
    # Get and validate account ID
    local account_id
    account_id=$(get_aws_config "account")
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    # Get and validate region
    local region
    region=$(get_aws_config "region")
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    # Display configuration
    echo -e "${GREEN}✅ AWS Account: $account_id${NC}"
    echo -e "${GREEN}✅ AWS Region: $region${NC}"
    
    # Export for use by other scripts
    export AWS_ACCOUNT_ID="$account_id"
    export AWS_REGION="$region"
    
    return 0
}

#
# Get resource name with account and region
#
# Usage: get_resource_name "prefix" "suffix"
# Example: get_resource_name "chatbot-vectors" "" -> "chatbot-vectors-123456789012-us-east-1"
#
get_resource_name() {
    local prefix="$1"
    local suffix="$2"
    
    if [ -z "$prefix" ]; then
        echo "ERROR: Resource prefix required" >&2
        return 1
    fi
    
    local account_id region
    account_id=$(get_aws_config "account") || return 1
    region=$(get_aws_config "region") || return 1
    
    if [ -n "$suffix" ]; then
        echo "${prefix}-${account_id}-${region}-${suffix}"
    else
        echo "${prefix}-${account_id}-${region}"
    fi
}

#
# Clear cached configuration (useful for testing or credential changes)
#
clear_aws_config_cache() {
    _AWS_ACCOUNT_ID=""
    _AWS_REGION=""
}

#
# Display current AWS configuration
#
show_aws_config() {
    echo -e "${CYAN}📊 Current AWS Configuration:${NC}"
    
    local account_id region
    account_id=$(get_aws_config "account" 2>/dev/null)
    region=$(get_aws_config "region" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo -e "   Account ID: ${account_id:-'Not detected'}"
        echo -e "   Region: ${region:-'Not detected'}"
    else
        echo -e "${YELLOW}   Configuration not available or invalid${NC}"
    fi
}
