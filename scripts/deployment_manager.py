#!/usr/bin/env python3
"""CDK deployment manager with rollback capability."""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from aws_config import get_aws_region

class DeploymentManager:
    """CDK deployment manager."""
    
    def __init__(self):
        self.stack_name = "ChatbotRagStack"
        self.region = get_aws_region()
    
    def deploy(self, args) -> int:
        """Execute CDK deployment."""
        try:
            print("🚀 Starting CDK deployment...")
            
            # Check CDK bootstrap
            self._ensure_cdk_bootstrap()
            
            # Install dependencies
            self._install_dependencies()
            
            # Deploy with CDK
            self._deploy_cdk()
            
            # Post-deployment configuration
            self._post_deployment_setup()
            
            print("✅ Deployment completed successfully")
            return 0
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            return 1
    
    def _ensure_cdk_bootstrap(self):
        """Ensure CDK is bootstrapped."""
        print("🔍 Checking CDK bootstrap...")
        try:
            result = subprocess.run([
                'cdk', 'doctor', '--region', self.region
            ], capture_output=True, text=True, timeout=30)
            
            if "not bootstrapped" in result.stdout or "not bootstrapped" in result.stderr:
                print("🔧 Bootstrapping CDK...")
                subprocess.run([
                    'cdk', 'bootstrap', '--region', self.region
                ], check=True, timeout=300)
        except subprocess.TimeoutExpired:
            print("⚠️  CDK bootstrap check timed out, proceeding...")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  CDK bootstrap failed: {e}")
    
    def _install_dependencies(self):
        """Install required dependencies."""
        print("📦 Installing dependencies...")
        
        # Check if we're in a virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        
        if not in_venv:
            print("⚠️  Not in virtual environment, skipping pip install")
            print("💡 Dependencies should be installed in a virtual environment")
        else:
            # Install Python dependencies only if in venv
            subprocess.run([
                'pip', 'install', '-r', 'requirements.txt'
            ], check=True, timeout=300)
        
        # Check if package.json exists for CDK dependencies
        if Path('package.json').exists():
            subprocess.run([
                'npm', 'install'
            ], check=True, timeout=300, cwd=Path.cwd())
        else:
            print("📦 No package.json found, skipping npm install")
    
    def _deploy_cdk(self):
        """Deploy using CDK."""
        print("🚀 Deploying infrastructure with CDK...")
        
        # Set CDK app path
        os.environ['CDK_DEFAULT_REGION'] = self.region
        
        # Deploy the stack
        subprocess.run([
            'cdk', 'deploy', 
            '--require-approval', 'never',
            '--region', self.region,
            '--app', 'python3 src/infrastructure/app.py'
        ], check=True, timeout=1800)
    
    def status(self, args) -> int:
        """Check deployment status."""
        try:
            print("🔍 Checking deployment status...")
            
            result = subprocess.run([
                'aws', 'cloudformation', 'describe-stacks',
                '--stack-name', self.stack_name,
                '--region', self.region
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                stack_info = json.loads(result.stdout)
                status = stack_info['Stacks'][0]['StackStatus']
                print(f"✅ Stack {self.stack_name}: {status}")
                
                # Show outputs if available
                outputs = stack_info['Stacks'][0].get('Outputs', [])
                if outputs:
                    print("\n📋 Stack Outputs:")
                    for output in outputs:
                        print(f"  {output['OutputKey']}: {output['OutputValue']}")
                
                return 0
            else:
                print("❌ Stack not found")
                return 1
        except subprocess.TimeoutExpired:
            print("⚠️  Status check timed out")
            return 1
        except json.JSONDecodeError:
            print("⚠️  Invalid response from AWS CLI")
            return 1
        except Exception as e:
            print(f"❌ Status check failed: {e}")
            return 1
    
    def _post_deployment_setup(self):
        """Handle post-deployment configuration and frontend upload."""
        print("🔧 Configuring application...")
        
        # Get stack outputs
        outputs = self._get_stack_outputs()
        
        # Configure widget with API endpoints
        self._configure_widget(outputs)
        
        # Upload frontend assets
        self._upload_frontend_assets(outputs)
        
        # Display summary
        self._display_summary(outputs)
    
    def _get_stack_outputs(self) -> Dict[str, str]:
        """Get CloudFormation stack outputs."""
        try:
            result = subprocess.run([
                'aws', 'cloudformation', 'describe-stacks',
                '--stack-name', self.stack_name,
                '--region', self.region
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception("Failed to get stack outputs")
            
            stack_info = json.loads(result.stdout)
            outputs = {}
            
            if stack_info['Stacks'] and stack_info['Stacks'][0].get('Outputs'):
                for output in stack_info['Stacks'][0]['Outputs']:
                    outputs[output['OutputKey']] = output['OutputValue']
            
            return outputs
        except Exception as e:
            raise Exception(f"Failed to get stack outputs: {e}")
    
    def _configure_widget(self, outputs: Dict[str, str]):
        """Generate widget-config.js with actual values."""
        template_path = Path("src/frontend/widget-config.template.js")
        config_path = Path("src/frontend/widget-config.js")
        
        if not template_path.exists():
            print("⚠️  Config template not found, skipping configuration")
            return
        
        # Read template
        with open(template_path, "r") as f:
            content = f.read()
        
        # Get actual values
        api_endpoint = outputs.get("ApiEndpoint", "")
        websocket_url = outputs.get("WebSocketApiUrl", "")
        api_key_arn = outputs.get("ApiKey", "")
        
        # Get actual API key value
        api_key_value = self._get_api_key_value(api_key_arn)
        
        # Replace placeholders
        content = content.replace("PLACEHOLDER_API_ENDPOINT", api_endpoint)
        content = content.replace("PLACEHOLDER_WEBSOCKET_URL", websocket_url)
        content = content.replace("PLACEHOLDER_API_KEY", api_key_value)
        
        # Write config file
        with open(config_path, "w") as f:
            f.write(content)
        
        print("✅ Widget config file generated")
    
    def _get_api_key_value(self, api_key_arn: str) -> str:
        """Get actual API key value from ARN."""
        if not api_key_arn:
            return ""
        
        key_id = api_key_arn.split('/')[-1]
        
        result = subprocess.run([
            'aws', 'apigateway', 'get-api-key',
            '--api-key', key_id,
            '--include-value',
            '--region', self.region
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            key_data = json.loads(result.stdout)
            return key_data.get('value', '')
        
        return ""
    
    def _upload_frontend_assets(self, outputs: Dict[str, str]):
        """Upload frontend assets to S3."""
        website_bucket = outputs.get("WebsiteBucketName")
        if not website_bucket:
            print("⚠️  Website bucket not found in outputs")
            return
        
        print(f"📤 Uploading frontend assets to {website_bucket}")
        
        # Upload widget.js
        widget_path = Path("src/frontend/widget.js")
        if widget_path.exists():
            subprocess.run([
                'aws', 's3', 'cp', str(widget_path), f's3://{website_bucket}/widget.js',
                '--content-type', 'application/javascript',
                '--region', self.region
            ], check=True)
            print("✅ Uploaded widget.js")
        
        # Upload widget-config.js
        config_path = Path("src/frontend/widget-config.js")
        if config_path.exists():
            subprocess.run([
                'aws', 's3', 'cp', str(config_path), f's3://{website_bucket}/widget-config.js',
                '--content-type', 'application/javascript',
                '--region', self.region
            ], check=True)
            print("✅ Uploaded widget-config.js")
        
        # Upload index.html
        index_path = Path("src/frontend/index.html")
        if index_path.exists():
            subprocess.run([
                'aws', 's3', 'cp', str(index_path), f's3://{website_bucket}/index.html',
                '--content-type', 'text/html',
                '--region', self.region
            ], check=True)
            print("✅ Uploaded index.html")
    
    def _display_summary(self, outputs: Dict[str, str]):
        """Display deployment summary."""
        cloudfront_domain = outputs.get("CloudFrontDomain")
        if cloudfront_domain:
            print("\n🎉 Deployment Summary:")
            print(f"📱 Demo Page: https://{cloudfront_domain}/index.html")
            print(f"🔗 Widget Script: https://{cloudfront_domain}/widget.js")
            print("\n💡 Add to your website:")
            print(f'<script src="https://{cloudfront_domain}/widget.js"></script>')
        else:
            print("⚠️  CloudFront domain not found in outputs")
    
    def rollback(self, args) -> int:
        """Rollback deployment."""
        try:
            print(f"🔄 Rolling back stack {self.stack_name}...")
            print("⏳ Note: CloudFront distribution deletion can take 15-45 minutes...")
            
            subprocess.run([
                'cdk', 'destroy', 
                '--force',
                '--region', self.region,
                '--app', 'python3 src/infrastructure/app.py'
            ], check=True, timeout=3000)  # 50 minutes timeout for CloudFront
            
            print("✅ Rollback completed")
            return 0
        except subprocess.TimeoutExpired:
            print("⚠️  Rollback timed out after 50 minutes")
            print("💡 CloudFront distributions can take up to 45 minutes to delete")
            print("   Check AWS Console to monitor deletion progress")
            return 1
        except subprocess.CalledProcessError as e:
            print(f"❌ Rollback failed: {e}")
            return 1
        except Exception as e:
            print(f"❌ Rollback failed: {e}")
            return 1
