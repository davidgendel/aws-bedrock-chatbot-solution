#!/usr/bin/env python3
"""
CDK app entry point for the chatbot RAG solution.
"""
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import aws_cdk as cdk

from src.infrastructure.cdk_stack import ChatbotRagStack


def main():
    """Main entry point for the CDK app."""
    try:
        app = cdk.App()
        
        # Get region from environment or use default
        region = os.environ.get("CDK_DEPLOY_REGION") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        
        # If no region in environment, try to load from config
        if not region:
            try:
                import json
                from pathlib import Path
                
                config_path = Path(__file__).parent.parent.parent / "config.json"
                if config_path.exists():
                    with open(config_path, "r") as f:
                        config = json.load(f)
                        region = config.get("region")
            except Exception:
                pass
        
        # Final fallback with warning
        if not region:
            region = "us-east-1"
            print("WARNING: No region specified, defaulting to us-east-1. Set AWS_REGION environment variable or region in config.json.")
        
        # Create the stack
        ChatbotRagStack(
            app, "ChatbotRagStack",
            env=cdk.Environment(
                account=os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ.get("CDK_DEFAULT_ACCOUNT")),
                region=region
            ),
            description="Serverless RAG chatbot solution with Graviton3 ARM64 architecture"
        )
        
        app.synth()
    except Exception as e:
        print(f"Error initializing CDK app: {e}")
        raise


if __name__ == "__main__":
    main()
