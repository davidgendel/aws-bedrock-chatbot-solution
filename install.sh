#!/bin/bash
#
# RAG Chatbot - One-Line Installer
# 
# Usage: curl -sSL https://raw.githubusercontent.com/user/repo/main/install.sh | bash
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
REPO_URL="https://github.com/your-github-username/aws-bedrock-chatbot-solution.git"
INSTALL_DIR="aws-bedrock-chatbot-solution"

# Welcome message
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║ 🤖 RAG Chatbot - One-Line Installer${NC}"
echo -e "${BLUE}║${NC}"
echo -e "${BLUE}║ This will download and deploy your AI chatbot in ~15 minutes${NC}"
echo -e "${BLUE}║ Monthly cost: Starting at \$29.76${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"

# Check prerequisites
echo -e "\n${CYAN}🔍 Checking system requirements...${NC}"

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git is not installed${NC}"
    echo -e "${YELLOW}💡 Install git first:${NC}"
    echo -e "   • Ubuntu/Debian: sudo apt install git"
    echo -e "   • macOS: xcode-select --install"
    echo -e "   • Windows: Download from git-scm.com"
    exit 1
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    echo -e "${YELLOW}💡 Install Python 3 first:${NC}"
    echo -e "   • Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo -e "   • macOS: brew install python3"
    echo -e "   • Windows: Download from python.org"
    exit 1
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${YELLOW}⚠️  AWS CLI not found. Installing...${NC}"
    
    # Try to install AWS CLI
    if command -v pip3 &> /dev/null; then
        pip3 install awscli --user --quiet
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo -e "${RED}❌ Cannot install AWS CLI automatically${NC}"
        echo -e "${YELLOW}💡 Install AWS CLI first:${NC}"
        echo -e "   • Visit: https://aws.amazon.com/cli/"
        exit 1
    fi
fi

# Check AWS credentials
echo -e "${CYAN}🔑 Checking AWS credentials...${NC}"
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${YELLOW}⚠️  AWS credentials not configured${NC}"
    echo -e "${CYAN}💡 Quick setup:${NC}"
    echo -e "   1. Go to AWS Console → IAM → Users → Your User → Security Credentials"
    echo -e "   2. Create new Access Key"
    echo -e "   3. Run: aws configure"
    echo -e "   4. Enter your Access Key and Secret Key"
    echo -e "\n${YELLOW}After setting up AWS credentials, run this installer again.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ System requirements met${NC}"

# Clone repository
echo -e "\n${CYAN}📥 Downloading chatbot code...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}⚠️  Directory $INSTALL_DIR already exists${NC}"
    read -p "Remove existing directory and continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
    else
        echo -e "${RED}❌ Installation cancelled${NC}"
        exit 1
    fi
fi

if ! git clone "$REPO_URL" "$INSTALL_DIR"; then
    echo -e "${RED}❌ Failed to download chatbot code${NC}"
    echo -e "${YELLOW}💡 Check your internet connection and try again${NC}"
    exit 1
fi

# Change to project directory
cd "$INSTALL_DIR"

# Make deploy script executable
chmod +x deploy.sh

# Run deployment
echo -e "\n${CYAN}🚀 Starting deployment...${NC}"
echo -e "${YELLOW}This will take about 15 minutes. Please be patient!${NC}"

if ! ./deploy.sh deploy; then
    echo -e "\n${RED}❌ Deployment failed${NC}"
    echo -e "${YELLOW}💡 Try running: ./deploy.sh rollback${NC}"
    echo -e "${YELLOW}💡 Or check: deployment.log${NC}"
    exit 1
fi

# Success message
echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║ 🎉 Success! Your AI chatbot is now live!${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${CYAN}📋 What's next:${NC}"
echo -e "   1. Add your documents to the 'documents' folder"
echo -e "   2. Run: python3 -m scripts.upload_documents --folder ./documents"
echo -e "   3. Copy the widget code to your website"

echo -e "\n${CYAN}📚 Documentation:${NC}"
echo -e "   • User guide: docs/user-guide.md"
echo -e "   • Troubleshooting: docs/troubleshooting.md"
echo -e "   • API docs: docs/api-spec.yaml"

echo -e "\n${CYAN}🆘 Need help?${NC}"
echo -e "   • GitHub Issues: https://github.com/your-github-username/aws-bedrock-chatbot-solution/issues"
echo -e "   • Documentation: https://github.com/your-github-username/aws-bedrock-chatbot-solution/docs"

echo -e "\n${GREEN}✅ Installation complete! Enjoy your new AI assistant!${NC}"
