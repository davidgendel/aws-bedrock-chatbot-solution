#!/bin/bash

# Vector Environment Setup Script
# Source this script to set up environment variables for vector management

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up vector management environment...${NC}"

# Try to get from CloudFormation first
VECTOR_BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].Outputs[?OutputKey==`VectorBucketName`].OutputValue' --output text 2>/dev/null || echo "")
VECTOR_INDEX_NAME=$(aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].Outputs[?OutputKey==`VectorIndexName`].OutputValue' --output text 2>/dev/null || echo "")

# Fallback to manual values if CloudFormation fails
if [ -z "$VECTOR_BUCKET_NAME" ] || [ -z "$VECTOR_INDEX_NAME" ]; then
    echo -e "${YELLOW}⚠️  Could not get configuration from CloudFormation, using manual values${NC}"
    VECTOR_BUCKET_NAME="chatbot-vectors-665832733337-us-east-1"
    VECTOR_INDEX_NAME="chatbot-document-vectors"
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
