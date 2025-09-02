#!/usr/bin/env python3
"""
Deployment script for the chatbot RAG solution.
"""
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ANSI colors for output formatting
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color

# Script variables
CONFIG_FILE = "config.json"
STACK_NAME = "ChatbotRagStack"


def section(title: str):
    """Display section header."""
    print(f"\n{BLUE}=== {title} ==={NC}")


def error(message: str):
    """Display error message and exit."""
    print(f"{RED}Error: {message}{NC}")
    sys.exit(1)


def warning(message: str):
    """Display warning message."""
    print(f"{YELLOW}Warning: {message}{NC}")


def success(message: str):
    """Display success message."""
    print(f"{GREEN}{message}{NC}")


def command_exists(command: str) -> bool:
    """Check if a command exists."""
    return shutil.which(command) is not None


def run_command(command: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command safely without shell=True."""
    # Parse the command string into a list of arguments
    args = shlex.split(command)
    return subprocess.run(args, check=check, text=True, capture_output=True)


def check_prerequisites():
    """Check prerequisites."""
    section("Checking Prerequisites")

    # Check if config.json exists
    if not Path(CONFIG_FILE).exists():
        error(f"{CONFIG_FILE} not found. Please ensure the configuration file exists.")

    # Parse region from config
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    
    region = config.get("region") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        warning("No region specified in config or environment, defaulting to us-east-1")
        region = "us-east-1"
    else:
        print(f"Using region: {region}")

    # Validate region format
    import re
    if not re.match(r"^[a-z]{2}-[a-z]+-[0-9]+$", region):
        error(f"Invalid region format: {region}. Expected format: us-east-1, eu-west-1, etc.")

    # Check AWS CLI is installed
    if not command_exists("aws"):
        error("AWS CLI is not installed. Please install it from https://aws.amazon.com/cli/")

    # Check AWS credentials
    print("Checking AWS credentials...")
    try:
        run_command(f"aws sts get-caller-identity --region {region}")
    except subprocess.CalledProcessError:
        error("AWS credentials not configured or invalid. Please run 'aws configure' to set up your credentials.")
    success("AWS credentials valid")

    # Check Python is installed
    if not command_exists("python3"):
        error("Python 3 is not installed. Please install it from https://www.python.org/")

    # Check Python version
    python_version = run_command("python3 --version", check=False).stdout
    if python_version:
        import re
        version_match = re.search(r"Python (\d+)\.(\d+)\.(\d+)", python_version)
        if version_match:
            major, minor, patch = map(int, version_match.groups())
            if major < 3 or (major == 3 and minor < 12):
                warning(f"Python version {major}.{minor}.{patch} detected. This project recommends Python 3.12 or higher.")
            else:
                print(f"Python version: {major}.{minor}.{patch}")
        else:
            warning("Could not determine Python version.")
    else:
        warning("Could not determine Python version.")

    success("All prerequisites satisfied")


def install_dependencies():
    """Install dependencies."""
    section("Installing Dependencies")
    run_command("pip3 install -r requirements.txt")
    success("Dependencies installed")


def build_project():
    """Build the project."""
    section("Building Project")
    # Check if pyproject.toml exists (modern Python packaging)
    if Path("pyproject.toml").exists():
        run_command("pip3 install -e .")
        success("Build completed using pyproject.toml")
    else:
        warning("No pyproject.toml found, skipping build step")


def deploy_infrastructure(region: str):
    """Deploy infrastructure."""
    section("Deploying Infrastructure")
    print(f"Deploying with CDK to region {region}...")
    
    # First, ensure CDK app is properly built
    run_command(f"python3 -m src.infrastructure.app")
    
    # Check if CDK is bootstrapped in this account/region
    try:
        print("Checking if CDK is bootstrapped...")
        bootstrap_check = run_command(f"cdk doctor --region {region}", check=False)
        if "not bootstrapped" in bootstrap_check.stdout or "not bootstrapped" in bootstrap_check.stderr:
            print("CDK environment not bootstrapped. Bootstrapping now...")
            run_command(f"cdk bootstrap --region {region}")
        else:
            print("CDK environment already bootstrapped")
    except Exception as e:
        print(f"Warning: Could not check CDK bootstrap status: {e}")
        print("Attempting to bootstrap anyway...")
        try:
            run_command(f"cdk bootstrap --region {region}")
        except Exception as bootstrap_error:
            print(f"Bootstrap warning: {bootstrap_error}")
    
    # Deploy the stack
    try:
        run_command(f"cdk deploy --require-approval never --region {region}")
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if e.stderr else e.stdout
        error(f"CDK deployment failed: {error_message}")
    
    success("Infrastructure deployed")


def configure_application(region: str):
    """Configure the application."""
    section("Configuring Application")
    print("Getting deployment outputs...")
    
    # Get stack outputs
    # Use signed client for enhanced security
    try:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent.parent / "lambda_function"))
        from aws_client_factory import AWSClientFactory
        cf_client = AWSClientFactory.create_client("cloudformation", region_name=region, enable_signing=True)
    except ImportError:
        cf_client = boto3.client("cloudformation", region_name=region)
    try:
        response = cf_client.describe_stacks(StackName=STACK_NAME)
        outputs = {}
        
        if response["Stacks"] and response["Stacks"][0]["Outputs"]:
            for output in response["Stacks"][0]["Outputs"]:
                outputs[output["OutputKey"]] = output["OutputValue"]
    except Exception as e:
        error(f"Failed to get stack outputs: {e}")
    
    # Extract values from outputs
    api_endpoint = outputs.get("ApiEndpoint")
    cloudfront_domain = outputs.get("CloudFrontDomain")
    document_bucket = outputs.get("DocumentBucketName")
    website_bucket = outputs.get("WebsiteBucketName")
    api_key_id = outputs.get("ApiKeyId")
    websocket_url = outputs.get("WebSocketApiUrl")
    
    # Validate required outputs
    if not all([api_endpoint, cloudfront_domain, document_bucket, website_bucket, api_key_id]):
        error("Missing required stack outputs")
    
    # Get API key value
    print("Getting API key...")
    try:
        apigw_client = AWSClientFactory.create_client("apigateway", region_name=region, enable_signing=True)
    except:
        apigw_client = boto3.client("apigateway", region_name=region)
    try:
        response = apigw_client.get_api_key(
            apiKey=api_key_id,
            includeValue=True
        )
        api_key = response["value"]
    except Exception as e:
        error(f"Failed to get API key: {e}")
    
    # Update widget.js with API endpoint, key, and WebSocket URL
    print("Updating widget.js with deployment values...")
    widget_path = Path("src/frontend/widget.js")
    if widget_path.exists():
        # Create a backup of the original file
        shutil.copy(widget_path, f"{widget_path}.bak")
        
        # Read the file
        with open(widget_path, "r") as f:
            content = f.read()
        
        # Replace placeholders
        content = content.replace("API_ENDPOINT_PLACEHOLDER", api_endpoint)
        content = content.replace("API_KEY_PLACEHOLDER", api_key)
        
        # Only replace WebSocket URL if it exists
        if websocket_url:
            content = content.replace("WEBSOCKET_URL_PLACEHOLDER", websocket_url)
        else:
            warning("WebSocket URL not found in stack outputs, streaming may not work")
            content = content.replace("WEBSOCKET_URL_PLACEHOLDER", "")
        
        # Write the updated file
        with open(widget_path, "w") as f:
            f.write(content)
        
        success("Widget configuration updated")
    else:
        error(f"{widget_path} not found")
    
    return {
        "api_endpoint": api_endpoint,
        "cloudfront_domain": cloudfront_domain,
        "document_bucket": document_bucket,
        "website_bucket": website_bucket,
        "api_key": api_key,
        "websocket_url": websocket_url
    }


def upload_frontend_assets(website_bucket: str, region: str):
    """Upload frontend assets."""
    section("Uploading Frontend Assets")
    print(f"Uploading to S3 bucket: {website_bucket}")
    
    try:
        s3_client = AWSClientFactory.create_client("s3", region_name=region, enable_signing=True)
    except:
        s3_client = boto3.client("s3", region_name=region)
    
    # Upload widget.js
    widget_path = Path("src/frontend/widget.js")
    if widget_path.exists():
        s3_client.upload_file(
            str(widget_path),
            website_bucket,
            "widget.js",
            ExtraArgs={"ContentType": "application/javascript"}
        )
        print(f"Uploaded {widget_path}")
    else:
        warning(f"{widget_path} not found, skipping")
    
    # Upload index.html
    index_path = Path("src/frontend/index.html")
    if index_path.exists():
        s3_client.upload_file(
            str(index_path),
            website_bucket,
            "index.html",
            ExtraArgs={"ContentType": "text/html"}
        )
        print(f"Uploaded {index_path}")
    else:
        warning(f"{index_path} not found, skipping")
    
    success("Frontend assets uploaded")






def display_summary(outputs: Dict[str, str]):
    """Display deployment summary."""
    section("Deployment Summary")
    print(f"API Endpoint: {YELLOW}{outputs['api_endpoint']}{NC}")
    print(f"CloudFront Domain: {YELLOW}{outputs['cloudfront_domain']}{NC}")
    print(f"Document Bucket: {YELLOW}{outputs['document_bucket']}{NC}")
    print(f"Website Bucket: {YELLOW}{outputs['website_bucket']}{NC}")
    if outputs.get("websocket_url"):
        print(f"WebSocket URL: {YELLOW}{outputs['websocket_url']}{NC}")
    
    section("Integration Instructions")
    print("Add the following code to your website:")
    print(f"{YELLOW}<script src=\"https://{outputs['cloudfront_domain']}/widget.js\"></script>")
    print("<script>")
    print("  SmallBizChatbot.init({")
    print("    containerId: 'chatbot-container',")
    print("    theme: {")
    print("      primaryColor: '#4287f5',")
    print("      fontFamily: 'Arial, sans-serif'")
    print("    }")
    print("  });")
    print("</script>")
    print(f"<div id=\"chatbot-container\"></div>{NC}")
    
    section("Demo Page")
    print(f"View the demo page at: {YELLOW}https://{outputs['cloudfront_domain']}/index.html{NC}")
    print(f"\n{YELLOW}Note: It may take a few minutes for the CloudFront distribution to fully deploy.{NC}")
    
    section("Next Steps")
    print("1. Use './process_documents --folder ./rag-docs' to add documents to your knowledge base")
    print("2. Customize the widget appearance using the theme options")
    print("3. Monitor usage in the AWS CloudWatch console")
    
    success("Deployment completed successfully!")


def main():
    """Main entry point."""
    try:
        # Check prerequisites
        check_prerequisites()
        
        # Load configuration
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        
        region = config.get("region", "us-east-1")
        
        # Install dependencies
        install_dependencies()
        
        # Build project
        build_project()
        
        # Deploy infrastructure
        deploy_infrastructure(region)
        
        # Configure application
        outputs = configure_application(region)
        
        # Upload frontend assets
        upload_frontend_assets(outputs["website_bucket"], region)
        
        # Display summary
        display_summary(outputs)
    except Exception as e:
        error(f"Deployment failed: {e}")


if __name__ == "__main__":
    main()
