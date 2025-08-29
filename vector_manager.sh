#!/bin/bash

# Vector Index Management Wrapper Script
# This script automatically sets environment variables and provides easy access to vector management commands

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to get deployment configuration
get_deployment_config() {
    print_info "Getting deployment configuration..."
    
    # Source common configuration library
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/scripts/common/aws_config.sh" ]; then
        source "$SCRIPT_DIR/scripts/common/aws_config.sh"
    else
        print_error "Cannot find AWS configuration library"
        print_warning "Please ensure scripts/common/aws_config.sh exists"
        return 1
    fi
    
    # Validate AWS environment
    if ! validate_aws_environment >/dev/null 2>&1; then
        print_error "AWS environment validation failed"
        print_warning "Please ensure AWS CLI is configured: aws configure"
        return 1
    fi
    
    # Try to get from CloudFormation first
    VECTOR_BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].Outputs[?OutputKey==`VectorBucketName`].OutputValue' --output text 2>/dev/null || echo "")
    VECTOR_INDEX_NAME=$(aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].Outputs[?OutputKey==`VectorIndexName`].OutputValue' --output text 2>/dev/null || echo "")
    
    # Fallback to dynamic construction if CloudFormation fails
    if [ -z "$VECTOR_BUCKET_NAME" ] || [ -z "$VECTOR_INDEX_NAME" ] || [ "$VECTOR_BUCKET_NAME" = "None" ] || [ "$VECTOR_INDEX_NAME" = "None" ]; then
        print_warning "Could not get configuration from CloudFormation, constructing dynamically"
        
        # Get AWS account and region dynamically
        local account_id region
        account_id=$(get_aws_config "account")
        region=$(get_aws_config "region")
        
        if [ $? -ne 0 ]; then
            print_error "Failed to get AWS configuration"
            return 1
        fi
        
        # Construct resource names dynamically
        VECTOR_BUCKET_NAME="chatbot-vectors-${account_id}-${region}"
        VECTOR_INDEX_NAME="chatbot-document-vectors"
        
        print_warning "Using dynamically constructed names"
    else
        print_success "Got configuration from CloudFormation"
    fi
    
    # Export environment variables
    export VECTOR_BUCKET_NAME
    export VECTOR_INDEX_NAME
    
    echo -e "${CYAN}📊 Configuration:${NC}"
    echo "   Vector Bucket: $VECTOR_BUCKET_NAME"
    echo "   Vector Index: $VECTOR_INDEX_NAME"
    echo ""
}

# Function to show usage
show_usage() {
    echo -e "${CYAN}🔧 Vector Index Management Tool${NC}"
    echo ""
    echo "Usage: $0 <command> [arguments]"
    echo ""
    echo "Available commands:"
    echo "  list                    List all vector indexes"
    echo "  info <index-name>       Show detailed index information"
    echo "  optimize <index-name>   Optimize vector index performance"
    echo "  stats                   Show comprehensive statistics"
    echo "  clear-cache            Clear all vector caches"
    echo "  create <index-name>    Create a new vector index"
    echo "  delete <index-name>    Delete a vector index"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 info chatbot-document-vectors"
    echo "  $0 optimize chatbot-document-vectors"
    echo "  $0 stats"
    echo "  $0 clear-cache"
    echo ""
    echo "Note: This script automatically sets the required environment variables."
}

# Main script logic
main() {
    # Check if command is provided
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    # Get deployment configuration
    get_deployment_config
    
    # Execute the vector management command
    case "$1" in
        "list")
            print_info "Listing vector indexes..."
            python3 scripts/manage_vector_indexes.py list
            ;;
        "info")
            if [ -z "$2" ]; then
                print_error "Index name required for info command"
                echo "Usage: $0 info <index-name>"
                exit 1
            fi
            print_info "Getting information for index: $2"
            python3 scripts/manage_vector_indexes.py info "$2"
            ;;
        "optimize")
            if [ -z "$2" ]; then
                print_error "Index name required for optimize command"
                echo "Usage: $0 optimize <index-name>"
                echo "Default index: $VECTOR_INDEX_NAME"
                echo "Running optimization on default index..."
                python3 scripts/manage_vector_indexes.py optimize "$VECTOR_INDEX_NAME"
            else
                print_info "Optimizing index: $2"
                python3 scripts/manage_vector_indexes.py optimize "$2"
            fi
            ;;
        "stats")
            print_info "Getting comprehensive statistics..."
            python3 scripts/manage_vector_indexes.py stats
            ;;
        "clear-cache")
            print_info "Clearing all vector caches..."
            python3 scripts/manage_vector_indexes.py clear-cache
            ;;
        "create")
            if [ -z "$2" ]; then
                print_error "Index name required for create command"
                echo "Usage: $0 create <index-name>"
                exit 1
            fi
            print_info "Creating index: $2"
            python3 scripts/manage_vector_indexes.py create "$2"
            ;;
        "delete")
            if [ -z "$2" ]; then
                print_error "Index name required for delete command"
                echo "Usage: $0 delete <index-name>"
                exit 1
            fi
            print_warning "Deleting index: $2"
            python3 scripts/manage_vector_indexes.py delete "$2"
            ;;
        "--help"|"-h"|"help")
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
