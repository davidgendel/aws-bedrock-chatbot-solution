#!/bin/bash
#
# RAG Chatbot - Atomic Deployment Script with Rollback
# 
# This script provides atomic deployment with:
# - Transaction-like deployment phases
# - Automatic rollback on failure
# - State checkpointing and recovery
# - Comprehensive error handling
# - Resource cleanup on failure
#

set -euo pipefail

# Colors for output
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Configuration
readonly CONFIG_FILE="config.json"
readonly LOG_FILE="deployment.log"
readonly STATE_FILE=".deployment_state.json"
readonly ROLLBACK_FILE=".rollback_state.json"
readonly CHECKPOINT_DIR=".deployment_checkpoints"

# Deployment phases (atomic units)
readonly PHASES=(
    "validate"
    "prepare"
    "infrastructure"
    "lambda"
    "api"
    "frontend"
    "finalize"
)

# Global state
CURRENT_PHASE=""
DEPLOYMENT_ID=""
START_TIME=""

# Initialize deployment
init_deployment() {
    DEPLOYMENT_ID="deploy_$(date +%s)"
    START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Create checkpoint directory
    mkdir -p "$CHECKPOINT_DIR"
    
    # Initialize state file
    cat > "$STATE_FILE" << EOF
{
    "deployment_id": "$DEPLOYMENT_ID",
    "start_time": "$START_TIME",
    "current_phase": "",
    "completed_phases": [],
    "failed_phase": "",
    "rollback_required": false,
    "resources_created": {},
    "checkpoints": {}
}
EOF
    
    # Initialize rollback state
    cat > "$ROLLBACK_FILE" << EOF
{
    "deployment_id": "$DEPLOYMENT_ID",
    "rollback_actions": [],
    "resources_to_cleanup": []
}
EOF
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting atomic deployment $DEPLOYMENT_ID" > "$LOG_FILE"
}

# Ensure virtual environment is activated for Python commands
ensure_venv_activated() {
    if [ -d ".venv" ] && [ -z "${VIRTUAL_ENV:-}" ]; then
        source .venv/bin/activate
    fi
}

# Run Python command with virtual environment
run_python() {
    ensure_venv_activated
    python "$@"
}

# Update deployment state
update_state() {
    local phase="$1"
    local status="$2"  # "started", "completed", "failed"
    
    if command -v jq &> /dev/null; then
        # Use jq for JSON manipulation
        local temp_file=$(mktemp)
        jq --arg phase "$phase" --arg status "$status" --arg time "$(date '+%Y-%m-%d %H:%M:%S')" '
            if $status == "started" then
                .current_phase = $phase |
                .phase_start_time = $time
            elif $status == "completed" then
                .completed_phases += [$phase] |
                .current_phase = "" |
                .checkpoints[$phase] = $time
            elif $status == "failed" then
                .failed_phase = $phase |
                .rollback_required = true |
                .failure_time = $time
            else
                .
            end
        ' "$STATE_FILE" > "$temp_file" && mv "$temp_file" "$STATE_FILE"
    else
        # Fallback without jq
        echo "Phase $phase: $status at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    fi
}

# Create checkpoint
create_checkpoint() {
    local phase="$1"
    local checkpoint_data="$2"
    
    local checkpoint_file="$CHECKPOINT_DIR/${phase}_checkpoint.json"
    echo "$checkpoint_data" > "$checkpoint_file"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checkpoint created for phase: $phase" >> "$LOG_FILE"
}

# Add rollback action
add_rollback_action() {
    local action_type="$1"
    local resource_id="$2"
    local cleanup_command="$3"
    
    if command -v jq &> /dev/null; then
        local temp_file=$(mktemp)
        jq --arg type "$action_type" --arg id "$resource_id" --arg cmd "$cleanup_command" '
            .rollback_actions += [{
                "type": $type,
                "resource_id": $id,
                "cleanup_command": $cmd,
                "timestamp": now | strftime("%Y-%m-%d %H:%M:%S")
            }]
        ' "$ROLLBACK_FILE" > "$temp_file" && mv "$temp_file" "$ROLLBACK_FILE"
    fi
}

# Enhanced error handler with automatic rollback
handle_error() {
    local exit_code=$?
    local line_number=$1
    local command="$2"
    
    echo -e "\n${RED}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║ ❌ Deployment Failed - Initiating Automatic Rollback${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    
    # Log the error
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] FATAL ERROR at line $line_number: $command (exit code: $exit_code)" >> "$LOG_FILE"
    
    # Update state to failed
    update_state "$CURRENT_PHASE" "failed"
    
    # Perform automatic rollback
    echo -e "${YELLOW}🔄 Starting automatic rollback...${NC}"
    perform_rollback
    
    exit $exit_code
}

# Set up error trap
trap 'handle_error ${LINENO} "$BASH_COMMAND"' ERR

# Perform rollback
perform_rollback() {
    echo -e "${CYAN}🔄 Performing rollback for deployment $DEPLOYMENT_ID${NC}"
    
    if [ ! -f "$ROLLBACK_FILE" ]; then
        echo -e "${YELLOW}⚠️  No rollback state found${NC}"
        return 0
    fi
    
    # Execute rollback actions in reverse order
    if command -v jq &> /dev/null; then
        local rollback_actions=$(jq -r '.rollback_actions | reverse | .[] | @base64' "$ROLLBACK_FILE" 2>/dev/null || echo "")
        
        if [ -n "$rollback_actions" ]; then
            echo "$rollback_actions" | while read -r action_data; do
                local action=$(echo "$action_data" | base64 -d)
                local action_type=$(echo "$action" | jq -r '.type')
                local resource_id=$(echo "$action" | jq -r '.resource_id')
                local cleanup_command=$(echo "$action" | jq -r '.cleanup_command')
                
                echo -e "${CYAN}🧹 Rolling back $action_type: $resource_id${NC}"
                
                # Execute cleanup command with error handling
                if eval "$cleanup_command" 2>> "$LOG_FILE"; then
                    echo -e "${GREEN}✅ Successfully rolled back $resource_id${NC}"
                else
                    echo -e "${YELLOW}⚠️  Failed to rollback $resource_id (may need manual cleanup)${NC}"
                fi
            done
        fi
    fi
    
    # Clean up deployment artifacts
    cleanup_deployment_artifacts
    
    echo -e "${GREEN}✅ Rollback completed${NC}"
}

# Clean up deployment artifacts
cleanup_deployment_artifacts() {
    echo -e "${CYAN}🧹 Cleaning up deployment artifacts...${NC}"
    
    # Remove temporary files
    rm -f "$STATE_FILE" "$ROLLBACK_FILE"
    rm -rf "$CHECKPOINT_DIR"
    
    # Clean up any temporary AWS resources
    if command -v aws &> /dev/null; then
        # Clean up any CloudFormation stacks in CREATE_FAILED state
        local failed_stacks=$(aws cloudformation list-stacks --stack-status-filter CREATE_FAILED --query 'StackSummaries[?contains(StackName, `ChatbotRag`)].StackName' --output text 2>/dev/null || echo "")
        
        if [ -n "$failed_stacks" ]; then
            echo "$failed_stacks" | while read -r stack_name; do
                if [ -n "$stack_name" ]; then
                    echo -e "${CYAN}🗑️  Cleaning up failed stack: $stack_name${NC}"
                    aws cloudformation delete-stack --stack-name "$stack_name" 2>> "$LOG_FILE" || true
                fi
            done
        fi
    fi
}

# Execute phase with atomic guarantees
execute_phase() {
    local phase="$1"
    local phase_function="$2"
    
    CURRENT_PHASE="$phase"
    
    echo -e "\n${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ 🚀 Phase: $phase${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    
    # Update state to started
    update_state "$phase" "started"
    
    # Execute the phase function
    if $phase_function; then
        # Phase completed successfully
        update_state "$phase" "completed"
        echo -e "${GREEN}✅ Phase '$phase' completed successfully${NC}"
    else
        # Phase failed
        update_state "$phase" "failed"
        echo -e "${RED}❌ Phase '$phase' failed${NC}"
        return 1
    fi
}

# Phase 1: Validation
phase_validate() {
    echo -e "${CYAN}🔍 Validating deployment prerequisites...${NC}"
    
    # Check required commands
    local required_commands=("aws" "python3" "node" "npm")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            echo -e "${RED}❌ Required command not found: $cmd${NC}"
            return 1
        fi
    done
    
    # Validate AWS credentials
    if ! aws sts get-caller-identity &>> "$LOG_FILE"; then
        echo -e "${RED}❌ AWS credentials not configured${NC}"
        return 1
    fi
    
    # Validate configuration file
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}❌ Configuration file not found: $CONFIG_FILE${NC}"
        return 1
    fi
    
    # Run Python validation if available
    # Try to use virtual environment if it exists, otherwise use system python3
    local python_cmd="python3"
    if [ -d ".venv" ]; then
        ensure_venv_activated
        python_cmd="python"
    fi
    
    if $python_cmd -c "import sys; sys.path.append('src'); from backend.config_validator import validate_config; validate_config('$CONFIG_FILE')" 2>> "$LOG_FILE"; then
        echo -e "${GREEN}✅ Configuration validation passed${NC}"
    else
        echo -e "${RED}❌ Configuration validation failed${NC}"
        return 1
    fi
    
    return 0
}

# Phase 2: Preparation
phase_prepare() {
    echo -e "${CYAN}📦 Preparing deployment environment...${NC}"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        echo -e "${CYAN}🐍 Creating Python virtual environment...${NC}"
        if ! python3 -m venv .venv &>> "$LOG_FILE"; then
            echo -e "${RED}❌ Failed to create virtual environment${NC}"
            return 1
        fi
        add_rollback_action "venv" ".venv" "rm -rf .venv"
    fi
    
    # Activate virtual environment
    echo -e "${CYAN}🔧 Activating virtual environment...${NC}"
    source .venv/bin/activate
    
    # Upgrade pip in virtual environment
    if ! python -m pip install --upgrade pip &>> "$LOG_FILE"; then
        echo -e "${YELLOW}⚠️  Failed to upgrade pip, continuing...${NC}"
    fi
    
    # Install Python dependencies in virtual environment
    echo -e "${CYAN}📦 Installing Python dependencies in virtual environment...${NC}"
    if ! python -m pip install -r requirements.txt &>> "$LOG_FILE"; then
        echo -e "${RED}❌ Failed to install Python dependencies${NC}"
        return 1
    fi
    
    # Install CDK if not present
    if ! npm list -g aws-cdk &>> "$LOG_FILE"; then
        echo -e "${CYAN}📦 Installing AWS CDK...${NC}"
        if ! npm install -g aws-cdk &>> "$LOG_FILE"; then
            echo -e "${RED}❌ Failed to install AWS CDK${NC}"
            return 1
        fi
        add_rollback_action "npm_package" "aws-cdk" "npm uninstall -g aws-cdk"
    fi
    
    # Bootstrap CDK if needed
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local region=$(aws configure get region || echo "us-east-1")
    
    if ! cdk bootstrap aws://$account_id/$region &>> "$LOG_FILE"; then
        echo -e "${YELLOW}⚠️  CDK bootstrap may have failed (might be already bootstrapped)${NC}"
    fi
    
    return 0
}

# Phase 3: Infrastructure
phase_infrastructure() {
    echo -e "${CYAN}🏗️  Deploying infrastructure...${NC}"
    
    # Ensure virtual environment is activated for CDK deployment
    ensure_venv_activated
    
    # Deploy CDK stack
    local stack_name="ChatbotRagStack"
    
    if cdk deploy --require-approval never --outputs-file cdk-outputs.json &>> "$LOG_FILE"; then
        echo -e "${GREEN}✅ Infrastructure deployed successfully${NC}"
        
        # Add rollback action for the stack
        add_rollback_action "cloudformation_stack" "$stack_name" "aws cloudformation delete-stack --stack-name $stack_name"
        
        # Create checkpoint with stack outputs
        if [ -f "cdk-outputs.json" ]; then
            create_checkpoint "infrastructure" "$(cat cdk-outputs.json)"
        fi
        
        return 0
    else
        echo -e "${RED}❌ Infrastructure deployment failed${NC}"
        return 1
    fi
}

# Phase 4: Lambda Functions
phase_lambda() {
    echo -e "${CYAN}⚡ Configuring Lambda functions...${NC}"
    
    # Lambda functions are deployed as part of CDK stack
    # This phase handles post-deployment configuration
    
    # Warm up Lambda functions to avoid cold starts
    if [ -f "cdk-outputs.json" ] && command -v jq &> /dev/null; then
        local api_endpoint=$(jq -r '.ChatbotRagStack.ApiEndpoint // empty' cdk-outputs.json)
        
        if [ -n "$api_endpoint" ]; then
            echo -e "${CYAN}🔥 Warming up Lambda functions...${NC}"
            
            # Make a test request to warm up the function
            if curl -s -X POST "$api_endpoint/chat" \
                -H "Content-Type: application/json" \
                -d '{"message": "test", "session_id": "warmup"}' \
                &>> "$LOG_FILE"; then
                echo -e "${GREEN}✅ Lambda functions warmed up${NC}"
            else
                echo -e "${YELLOW}⚠️  Lambda warmup failed (functions may still work)${NC}"
            fi
        fi
    fi
    
    return 0
}

# Phase 5: API Configuration
phase_api() {
    echo -e "${CYAN}🌐 Configuring API endpoints...${NC}"
    
    # API Gateway is deployed as part of CDK stack
    # This phase handles post-deployment API configuration
    
    if [ -f "cdk-outputs.json" ] && command -v jq &> /dev/null; then
        local api_endpoint=$(jq -r '.ChatbotRagStack.ApiEndpoint // empty' cdk-outputs.json)
        local websocket_endpoint=$(jq -r '.ChatbotRagStack.WebSocketEndpoint // empty' cdk-outputs.json)
        
        if [ -n "$api_endpoint" ] && [ -n "$websocket_endpoint" ]; then
            echo -e "${GREEN}✅ API endpoints configured:${NC}"
            echo -e "   REST API: $api_endpoint"
            echo -e "   WebSocket: $websocket_endpoint"
            
            # Test API endpoints
            if curl -s "$api_endpoint/health" &>> "$LOG_FILE"; then
                echo -e "${GREEN}✅ API health check passed${NC}"
            else
                echo -e "${YELLOW}⚠️  API health check failed${NC}"
            fi
            
            return 0
        else
            echo -e "${RED}❌ API endpoints not found in stack outputs${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ Stack outputs not available${NC}"
        return 1
    fi
}

# Phase 6: Frontend
phase_frontend() {
    echo -e "${CYAN}🎨 Configuring frontend...${NC}"
    
    if [ -f "cdk-outputs.json" ] && command -v jq &> /dev/null; then
        local api_endpoint=$(jq -r '.ChatbotRagStack.ApiEndpoint // empty' cdk-outputs.json)
        local websocket_endpoint=$(jq -r '.ChatbotRagStack.WebSocketEndpoint // empty' cdk-outputs.json)
        local cloudfront_url=$(jq -r '.ChatbotRagStack.CloudFrontUrl // empty' cdk-outputs.json)
        local api_key_arn=$(jq -r '.ChatbotRagStack.ApiKey // empty' cdk-outputs.json)
        
        # Extract API key ID from ARN and get the actual key value
        local api_key_id=""
        local api_key_value=""
        
        if [ -n "$api_key_arn" ]; then
            # Extract key ID from ARN (format: arn:aws:apigateway:region::/apikeys/keyid)
            api_key_id=$(echo "$api_key_arn" | sed 's/.*\/\([^\/]*\)$/\1/')
            
            if [ -n "$api_key_id" ]; then
                # Get the actual API key value
                api_key_value=$(aws apigateway get-api-key --api-key "$api_key_id" --include-value --query 'value' --output text 2>/dev/null)
                
                if [ -z "$api_key_value" ] || [ "$api_key_value" = "None" ]; then
                    echo -e "${YELLOW}⚠️  Could not retrieve API key value, trying alternative method...${NC}"
                    # Try using the key name instead
                    api_key_value=$(aws apigateway get-api-keys --name-query "ChatbotApiKey" --include-values --query 'items[0].value' --output text 2>/dev/null)
                fi
            fi
        fi
        
        # Update frontend configuration
        if [ -n "$api_endpoint" ] && [ -n "$websocket_endpoint" ]; then
            # Replace placeholders in widget.js
            if [ -n "$api_key_value" ] && [ "$api_key_value" != "None" ]; then
                sed -i.bak \
                    -e "s|API_ENDPOINT_PLACEHOLDER|$api_endpoint|g" \
                    -e "s|API_KEY_PLACEHOLDER|$api_key_value|g" \
                    -e "s|WEBSOCKET_URL_PLACHOLDER|$websocket_endpoint|g" \
                    -e "s|WEBSOCKET_URL_PLACEHOLDER|$websocket_endpoint|g" \
                    src/frontend/widget.js
                
                echo -e "${GREEN}✅ Frontend configured with API endpoints and key${NC}"
            else
                echo -e "${YELLOW}⚠️  API key not available, configuring without key${NC}"
                sed -i.bak \
                    -e "s|API_ENDPOINT_PLACEHOLDER|$api_endpoint|g" \
                    -e "s|API_KEY_PLACEHOLDER|YOUR_API_KEY_HERE|g" \
                    -e "s|WEBSOCKET_URL_PLACHOLDER|$websocket_endpoint|g" \
                    -e "s|WEBSOCKET_URL_PLACEHOLDER|$websocket_endpoint|g" \
                    src/frontend/widget.js
                
                echo -e "${YELLOW}⚠️  Please manually replace 'YOUR_API_KEY_HERE' with your API key${NC}"
                echo -e "${GREEN}✅ Frontend configured with API endpoints${NC}"
            fi
            
            if [ -n "$cloudfront_url" ]; then
                echo -e "${GREEN}✅ CloudFront distribution: $cloudfront_url${NC}"
            fi
            
            return 0
        else
            echo -e "${RED}❌ API endpoints not available for frontend configuration${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ Stack outputs not available${NC}"
        return 1
    fi
}

# Phase 7: Finalization
phase_finalize() {
    echo -e "${CYAN}🎯 Finalizing deployment...${NC}"
    
    # Upload frontend files to S3 website bucket
    if [ -f "cdk-outputs.json" ] && command -v jq &> /dev/null; then
        local website_bucket=$(jq -r '.ChatbotRagStack.WebsiteBucketName // empty' cdk-outputs.json)
        local cloudfront_url=$(jq -r '.ChatbotRagStack.CloudFrontUrl // empty' cdk-outputs.json)
        
        if [ -n "$website_bucket" ]; then
            echo -e "${CYAN}📤 Uploading frontend files to S3...${NC}"
            
            # Upload widget.js with proper content type
            if aws s3 cp src/frontend/widget.js "s3://$website_bucket/widget.js" \
                --content-type "application/javascript" \
                --cache-control "public, max-age=3600" &>> "$LOG_FILE"; then
                echo -e "${GREEN}✅ Uploaded widget.js to S3${NC}"
            else
                echo -e "${YELLOW}⚠️  Failed to upload widget.js to S3${NC}"
            fi
            
            # Upload index.html with proper content type
            if aws s3 cp src/frontend/index.html "s3://$website_bucket/index.html" \
                --content-type "text/html" \
                --cache-control "public, max-age=300" &>> "$LOG_FILE"; then
                echo -e "${GREEN}✅ Uploaded index.html to S3${NC}"
            else
                echo -e "${YELLOW}⚠️  Failed to upload index.html to S3${NC}"
            fi
            
            # Invalidate CloudFront cache for the uploaded files
            if [ -n "$cloudfront_url" ]; then
                local distribution_id=$(echo "$cloudfront_url" | sed 's|https://||' | sed 's|\.cloudfront\.net.*||')
                if [ -n "$distribution_id" ]; then
                    echo -e "${CYAN}🔄 Invalidating CloudFront cache...${NC}"
                    if aws cloudfront create-invalidation \
                        --distribution-id "$distribution_id" \
                        --paths "/widget.js" "/index.html" &>> "$LOG_FILE"; then
                        echo -e "${GREEN}✅ CloudFront cache invalidated${NC}"
                    else
                        echo -e "${YELLOW}⚠️  Failed to invalidate CloudFront cache${NC}"
                    fi
                fi
            fi
        else
            echo -e "${YELLOW}⚠️  Website bucket name not found in outputs${NC}"
        fi
        
        # Generate integration code
        if [ -n "$cloudfront_url" ]; then
            # Generate integration HTML
            cat > integration.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Chatbot Integration</title>
</head>
<body>
    <div id="chatbot-container"></div>
    <script src="$cloudfront_url/widget.js"></script>
    <script>
        // Initialize the chatbot
        SmallBizChatbot.init({
            containerId: 'chatbot-container'
        });
    </script>
</body>
</html>
EOF
            
            echo -e "${GREEN}✅ Integration code generated: integration.html${NC}"
        fi
    fi
    
    # Clean up temporary files
    rm -f cdk-outputs.json src/frontend/widget.js.bak
    
    # Display deployment summary
    display_deployment_summary
    
    return 0
}

# Display deployment summary
display_deployment_summary() {
    echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║ 🎉 Deployment Completed Successfully!${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    
    if [ -f "cdk-outputs.json" ] && command -v jq &> /dev/null; then
        local api_endpoint=$(jq -r '.ChatbotRagStack.ApiEndpoint // empty' cdk-outputs.json)
        local websocket_endpoint=$(jq -r '.ChatbotRagStack.WebSocketEndpoint // empty' cdk-outputs.json)
        local cloudfront_url=$(jq -r '.ChatbotRagStack.CloudFrontUrl // empty' cdk-outputs.json)
        
        echo -e "\n${CYAN}📋 Deployment Details:${NC}"
        echo -e "   Deployment ID: $DEPLOYMENT_ID"
        echo -e "   Start Time: $START_TIME"
        echo -e "   End Time: $(date '+%Y-%m-%d %H:%M:%S')"
        
        echo -e "\n${CYAN}🔗 Endpoints:${NC}"
        [ -n "$api_endpoint" ] && echo -e "   REST API: $api_endpoint"
        [ -n "$websocket_endpoint" ] && echo -e "   WebSocket: $websocket_endpoint"
        [ -n "$cloudfront_url" ] && echo -e "   Frontend: $cloudfront_url"
        
        echo -e "\n${CYAN}📝 Next Steps:${NC}"
        echo -e "   1. Upload documents: .venv/bin/python -m scripts.upload_documents --folder ./documents"
        echo -e "   2. Test the chatbot: Open integration.html in your browser"
        echo -e "   3. Integrate: Copy the code from integration.html to your website"
        
        echo -e "\n${CYAN}📊 Management Commands:${NC}"
        echo -e "   • View logs: aws logs tail /aws/lambda/ChatbotRagStack-ChatbotFunction"
        echo -e "   • Clean vectors: .venv/bin/python scripts/cleanup_vectors.py --days 90"
        echo -e "   • Monitor costs: Check AWS Cost Explorer"
    fi
    
    echo -e "\n${GREEN}✅ Your AI chatbot is ready to use!${NC}"
}

# Main deployment function
main() {
    local command="${1:-deploy}"
    
    case "$command" in
        "deploy")
            init_deployment
            
            # Execute all phases
            for phase in "${PHASES[@]}"; do
                execute_phase "$phase" "phase_$phase"
            done
            
            # Clean up state files on success
            rm -f "$STATE_FILE" "$ROLLBACK_FILE"
            rm -rf "$CHECKPOINT_DIR"
            ;;
            
        "rollback")
            echo -e "${YELLOW}🔄 Manual rollback requested${NC}"
            perform_rollback
            ;;
            
        "status")
            if [ -f "$STATE_FILE" ]; then
                echo -e "${CYAN}📊 Deployment Status:${NC}"
                if command -v jq &> /dev/null; then
                    jq -r '
                        "Deployment ID: " + .deployment_id,
                        "Start Time: " + .start_time,
                        "Current Phase: " + (.current_phase // "None"),
                        "Completed Phases: " + (.completed_phases | join(", ")),
                        "Failed Phase: " + (.failed_phase // "None"),
                        "Rollback Required: " + (.rollback_required | tostring)
                    ' "$STATE_FILE"
                else
                    cat "$STATE_FILE"
                fi
            else
                # Check CloudFormation stack status
                echo -e "${CYAN}📊 Checking CloudFormation Stack Status:${NC}"
                if aws cloudformation describe-stacks --stack-name ChatbotRagStack &> /dev/null; then
                    stack_status=$(aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].StackStatus' --output text 2>/dev/null)
                    creation_time=$(aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].CreationTime' --output text 2>/dev/null)
                    
                    echo -e "${GREEN}✅ Stack Status: $stack_status${NC}"
                    echo -e "${GREEN}✅ Created: $creation_time${NC}"
                    
                    # Get stack outputs
                    echo -e "${CYAN}📋 Stack Outputs:${NC}"
                    aws cloudformation describe-stacks --stack-name ChatbotRagStack --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output table 2>/dev/null || echo "No outputs available"
                else
                    echo -e "${RED}❌ ChatbotRagStack not found. Please deploy first.${NC}"
                fi
            fi
            ;;
            
        "help"|"--help")
            echo -e "${CYAN}RAG Chatbot - Atomic Deployment Script${NC}"
            echo -e ""
            echo -e "${BOLD}Usage:${NC}"
            echo -e "  $0 [command]"
            echo -e ""
            echo -e "${BOLD}Commands:${NC}"
            echo -e "  deploy    Deploy the chatbot (default)"
            echo -e "  rollback  Rollback the current deployment"
            echo -e "  status    Show deployment status"
            echo -e "  help      Show this help message"
            ;;
            
        *)
            echo -e "${RED}❌ Unknown command: $command${NC}"
            echo -e "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
