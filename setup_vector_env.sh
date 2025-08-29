#!/bin/bash

# Vector Environment Setup Script
# Source this script to set up environment variables for vector management

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Source common configuration library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/scripts/common/aws_config.sh" ]; then
    source "$SCRIPT_DIR/scripts/common/aws_config.sh"
elif [ -f "./scripts/common/aws_config.sh" ]; then
    source "./scripts/common/aws_config.sh"
else
    echo -e "${RED}❌ Cannot find AWS configuration library${NC}"
    echo -e "${YELLOW}💡 Please run this script from the project root directory${NC}"
    return 1 2>/dev/null || exit 1
fi

echo -e "${BLUE}🔧 Setting up vector management environment...${NC}"

# Validate AWS environment first
if ! validate_aws_environment; then
    echo -e "${RED}❌ AWS environment validation failed${NC}"
    return 1 2>/dev/null || exit 1
fi

# Try to get from CloudFormation first
VECTOR_BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].Outputs[?OutputKey==`VectorBucketName`].OutputValue' --output text 2>/dev/null || echo "")
VECTOR_INDEX_NAME=$(aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].Outputs[?OutputKey==`VectorIndexName`].OutputValue' --output text 2>/dev/null || echo "")

# Fallback to dynamic construction if CloudFormation fails
if [ -z "$VECTOR_BUCKET_NAME" ] || [ -z "$VECTOR_INDEX_NAME" ] || [ "$VECTOR_BUCKET_NAME" = "None" ] || [ "$VECTOR_INDEX_NAME" = "None" ]; then
    echo -e "${YELLOW}⚠️  Could not get configuration from CloudFormation, constructing dynamically${NC}"
    
    # Get AWS account and region dynamically
    local account_id region
    account_id=$(get_aws_config "account")
    region=$(get_aws_config "region")
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to get AWS configuration${NC}"
        return 1 2>/dev/null || exit 1
    fi
    
    # Construct resource names dynamically
    VECTOR_BUCKET_NAME="chatbot-vectors-${account_id}-${region}"
    VECTOR_INDEX_NAME="chatbot-document-vectors"
    
    echo -e "${YELLOW}📊 Using dynamically constructed names:${NC}"
else
    echo -e "${GREEN}✅ Got configuration from CloudFormation${NC}"
fi

# Export environment variables
export VECTOR_BUCKET_NAME
export VECTOR_INDEX_NAME

echo -e "${GREEN}📊 Environment variables set:${NC}"
echo "   VECTOR_BUCKET_NAME=$VECTOR_BUCKET_NAME"
echo "   VECTOR_INDEX_NAME=$VECTOR_INDEX_NAME"
echo ""
echo -e "${BLUE}🚀 You can now run vector management commands directly:${NC}"
echo "   python3 scripts/manage_vector_indexes.py list"
echo "   python3 scripts/manage_vector_indexes.py info $VECTOR_INDEX_NAME"
echo "   python3 scripts/manage_vector_indexes.py optimize $VECTOR_INDEX_NAME"
echo "   python3 scripts/manage_vector_indexes.py stats"
echo ""
echo -e "${YELLOW}💡 Tip: Use './vector_manager.sh' for easier command management${NC}"
