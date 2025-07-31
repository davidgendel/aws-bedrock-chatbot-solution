#!/bin/bash
#
# S3 Bucket and S3 Vector Cleanup Script for RAG Chatbot
# 
# This script cleans up S3 buckets and S3 Vector buckets/indexes
# Use this if rollback fails or you need to manually clean up resources
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color
readonly BOLD='\033[1m'

# Configuration
readonly STACK_NAME="ChatbotRagStack"

echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                RAG Chatbot S3 & S3 Vector Cleanup                           ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo

# Function to delete S3 Vector index and bucket using correct S3 Vectors service CLI
delete_vector_resources() {
    local bucket_name="$1"
    local index_name="$2"
    
    echo -e "${CYAN}🗑️  Deleting S3 Vector resources: index $index_name in bucket $bucket_name${NC}"
    
    # First delete the index using correct camelCase CLI parameters
    if aws s3vectors get-index --vector-bucket-name "$bucket_name" --index-name "$index_name" >/dev/null 2>&1; then
        echo -e "${CYAN}      Deleting S3 Vector index...${NC}"
        if aws s3vectors delete-index --vector-bucket-name "$bucket_name" --index-name "$index_name" 2>/dev/null; then
            echo -e "${GREEN}   ✅ Successfully deleted S3 Vector index: $index_name${NC}"
        else
            echo -e "${YELLOW}   ⚠️  Failed to delete S3 Vector index: $index_name${NC}"
        fi
    else
        echo -e "${YELLOW}   ⚠️  S3 Vector index $index_name does not exist or is not accessible${NC}"
    fi
    
    # Then delete the vector bucket using correct camelCase CLI parameter
    if aws s3vectors get-vector-bucket --vector-bucket-name "$bucket_name" >/dev/null 2>&1; then
        echo -e "${CYAN}      Deleting S3 Vector bucket...${NC}"
        if aws s3vectors delete-vector-bucket --vector-bucket-name "$bucket_name" 2>/dev/null; then
            echo -e "${GREEN}   ✅ Successfully deleted S3 Vector bucket: $bucket_name${NC}"
        else
            echo -e "${YELLOW}   ⚠️  Failed to delete S3 Vector bucket: $bucket_name${NC}"
        fi
    else
        echo -e "${YELLOW}   ⚠️  S3 Vector bucket $bucket_name does not exist or is not accessible${NC}"
    fi
}

# Function to empty a single S3 bucket
empty_bucket() {
    local bucket_name="$1"
    local bucket_type="$2"
    
    echo -e "${CYAN}🗑️  Emptying $bucket_type bucket: $bucket_name${NC}"
    
    # Check if bucket exists
    if ! aws s3api head-bucket --bucket "$bucket_name" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Bucket $bucket_name does not exist or is not accessible${NC}"
        return 0
    fi
    
    # Get bucket location for progress tracking
    local object_count
    object_count=$(aws s3 ls "s3://$bucket_name" --recursive --summarize 2>/dev/null | grep "Total Objects:" | awk '{print $3}' || echo "0")
    
    if [ "$object_count" -eq 0 ]; then
        echo -e "${GREEN}✅ Bucket $bucket_name is already empty${NC}"
        return 0
    fi
    
    echo -e "${CYAN}   Found $object_count objects to delete${NC}"
    
    # Delete all current objects
    echo -e "${CYAN}   Deleting current objects...${NC}"
    aws s3 rm "s3://$bucket_name" --recursive --quiet 2>/dev/null || {
        echo -e "${YELLOW}⚠️  Some objects may have failed to delete${NC}"
    }
    
    # Handle versioned objects if versioning is enabled
    echo -e "${CYAN}   Checking for versioned objects...${NC}"
    local versions_exist=false
    
    # Check if there are any object versions
    if aws s3api list-object-versions --bucket "$bucket_name" --max-items 1 --output json 2>/dev/null | jq -e '.Versions // .DeleteMarkers | length > 0' >/dev/null 2>&1; then
        versions_exist=true
        echo -e "${CYAN}   Found versioned objects, deleting all versions...${NC}"
        
        # Delete all object versions
        aws s3api list-object-versions --bucket "$bucket_name" --output json --query 'Versions[].{Key:Key,VersionId:VersionId}' 2>/dev/null | \
        jq -r '.[]? | select(.VersionId != null) | "\(.Key)\t\(.VersionId)"' | \
        while IFS=$'\t' read -r key version_id; do
            if [ -n "$key" ] && [ -n "$version_id" ]; then
                aws s3api delete-object --bucket "$bucket_name" --key "$key" --version-id "$version_id" >/dev/null 2>&1 || true
            fi
        done
        
        # Delete all delete markers
        aws s3api list-object-versions --bucket "$bucket_name" --output json --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' 2>/dev/null | \
        jq -r '.[]? | select(.VersionId != null) | "\(.Key)\t\(.VersionId)"' | \
        while IFS=$'\t' read -r key version_id; do
            if [ -n "$key" ] && [ -n "$version_id" ]; then
                aws s3api delete-object --bucket "$bucket_name" --key "$key" --version-id "$version_id" >/dev/null 2>&1 || true
            fi
        done
    fi
    
    # Verify bucket is empty
    local remaining_objects
    remaining_objects=$(aws s3 ls "s3://$bucket_name" --recursive --summarize 2>/dev/null | grep "Total Objects:" | awk '{print $3}' || echo "0")
    
    if [ "$remaining_objects" -eq 0 ]; then
        echo -e "${GREEN}✅ Successfully emptied $bucket_type bucket: $bucket_name${NC}"
    else
        echo -e "${YELLOW}⚠️  Warning: $remaining_objects objects may still remain in $bucket_name${NC}"
    fi
}

# Main cleanup function
cleanup_chatbot_resources() {
    echo -e "${CYAN}🔍 Looking up resources from CloudFormation stack...${NC}"
    
    # Get stack outputs
    local stack_outputs
    if ! stack_outputs=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs' --output json 2>/dev/null); then
        echo -e "${RED}❌ Could not find CloudFormation stack: $STACK_NAME${NC}"
        echo -e "${YELLOW}💡 The stack may have already been deleted or doesn't exist${NC}"
        return 1
    fi
    
    # Extract resource names
    local vector_bucket vector_index_name metadata_bucket document_bucket
    vector_bucket=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="VectorBucketName") | .OutputValue' 2>/dev/null)
    vector_index_name=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="VectorIndexName") | .OutputValue' 2>/dev/null)
    metadata_bucket=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="MetadataBucketName") | .OutputValue' 2>/dev/null)
    document_bucket=$(echo "$stack_outputs" | jq -r '.[] | select(.OutputKey=="DocumentBucketName") | .OutputValue' 2>/dev/null)
    
    echo -e "${CYAN}📋 Found the following resources:${NC}"
    [ -n "$vector_bucket" ] && [ "$vector_bucket" != "null" ] && echo -e "   • S3 Vector bucket: $vector_bucket"
    [ -n "$vector_index_name" ] && [ "$vector_index_name" != "null" ] && echo -e "   • S3 Vector index: $vector_index_name"
    [ -n "$metadata_bucket" ] && [ "$metadata_bucket" != "null" ] && echo -e "   • Metadata bucket: $metadata_bucket"
    [ -n "$document_bucket" ] && [ "$document_bucket" != "null" ] && echo -e "   • Document bucket: $document_bucket"
    echo
    
    # Clean up S3 Vector resources first (if both bucket and index exist)
    local resources_processed=0
    
    if [ -n "$vector_bucket" ] && [ "$vector_bucket" != "null" ] && [ -n "$vector_index_name" ] && [ "$vector_index_name" != "null" ]; then
        delete_vector_resources "$vector_bucket" "$vector_index_name"
        ((resources_processed++))
    fi
    
    # Clean up regular S3 buckets
    if [ -n "$metadata_bucket" ] && [ "$metadata_bucket" != "null" ]; then
        empty_bucket "$metadata_bucket" "metadata"
        ((resources_processed++))
    fi
    
    if [ -n "$document_bucket" ] && [ "$document_bucket" != "null" ]; then
        empty_bucket "$document_bucket" "document"
        ((resources_processed++))
    fi
    
    if [ $resources_processed -eq 0 ]; then
        echo -e "${YELLOW}⚠️  No resources found to clean up${NC}"
    else
        echo -e "${GREEN}✅ Successfully processed $resources_processed resources${NC}"
    fi
}

# Show usage information
show_usage() {
    echo -e "${BOLD}Usage:${NC}"
    echo -e "  $0 [OPTIONS]"
    echo
    echo -e "${BOLD}Options:${NC}"
    echo -e "  --stack-name NAME    CloudFormation stack name (default: ChatbotRagStack)"
    echo -e "  --help              Show this help message"
    echo
    echo -e "${BOLD}Examples:${NC}"
    echo -e "  $0                           # Clean up default stack buckets"
    echo -e "  $0 --stack-name MyStack      # Clean up custom stack buckets"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed or not in PATH${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ jq is not installed or not in PATH${NC}"
    echo -e "${YELLOW}💡 Install jq: sudo apt-get install jq (Ubuntu/Debian) or brew install jq (macOS)${NC}"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured or invalid${NC}"
    echo -e "${YELLOW}💡 Run 'aws configure' to set up your credentials${NC}"
    exit 1
fi

# Confirm before proceeding
echo -e "${YELLOW}⚠️  This will permanently delete all objects in the chatbot S3 buckets.${NC}"
echo -e "${YELLOW}   This action cannot be undone!${NC}"
echo
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}🚫 Operation cancelled${NC}"
    exit 0
fi

# Perform cleanup
echo
cleanup_chatbot_resources

echo
echo -e "${GREEN}✅ Resource cleanup completed!${NC}"
echo -e "${CYAN}💡 You can now safely delete the CloudFormation stack if needed${NC}"
