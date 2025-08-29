#!/usr/bin/env python3
"""Atomic deployment manager with rollback capability."""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from aws_config import get_aws_region

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from backend.deployment_state_manager import DeploymentStateManager
except ImportError:
    class DeploymentStateManager:
        def save_state(self, state): pass
        def load_state(self): return {}
        def clear_state(self): pass

class DeploymentError(Exception):
    """Custom deployment exception."""
    pass

class AtomicDeployment:
    """Context manager for atomic deployments with rollback."""
    
    def __init__(self):
        self.lock_file = Path(".deployment.lock")
        self.resources_created = []
        self.state_manager = DeploymentStateManager()
    
    def __enter__(self):
        if self.lock_file.exists():
            raise DeploymentError("Another deployment is in progress")
        self.lock_file.write_text(str(os.getpid()))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._cleanup_resources()
        self.lock_file.unlink(missing_ok=True)
    
    def _cleanup_resources(self):
        """Cleanup resources on failure."""
        print("🔄 Rolling back deployment...")
        for resource in reversed(self.resources_created):
            try:
                self._delete_resource(resource)
            except Exception as e:
                print(f"⚠️  Failed to cleanup {resource}: {e}")
    
    def _delete_resource(self, resource: Dict[str, Any]):
        """Delete a single resource."""
        if resource['type'] == 'cloudformation':
            try:
                subprocess.run([
                    'aws', 'cloudformation', 'delete-stack', 
                    '--stack-name', resource['name'],
                    '--region', get_aws_region()
                ], check=True, timeout=300)
            except subprocess.TimeoutExpired:
                print(f"⚠️  Timeout deleting stack {resource['name']}")
            except subprocess.CalledProcessError as e:
                print(f"⚠️  Failed to delete stack {resource['name']}: {e}")

class DeploymentManager:
    """Main deployment manager."""
    
    def __init__(self):
        self.state_manager = DeploymentStateManager()
    
    def deploy(self, args) -> int:
        """Execute deployment with atomic operations."""
        try:
            with AtomicDeployment() as atomic:
                return self._execute_deployment(atomic, args)
        except DeploymentError as e:
            print(f"❌ Deployment failed: {e}")
            return 1
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return 1
    
    def _execute_deployment(self, atomic: AtomicDeployment, args) -> int:
        """Execute the actual deployment steps."""
        print("🚀 Starting deployment...")
        
        # Load existing configuration
        config = self._load_config()
        
        # Deploy CloudFormation stack
        stack_name = config.get('stack_name', 'bedrock-chatbot')
        self._deploy_cloudformation(atomic, stack_name)
        
        # Save deployment state
        state = {
            'stack_name': stack_name,
            'status': 'deployed',
            'resources': atomic.resources_created
        }
        self.state_manager.save_state(state)
        
        print("✅ Deployment completed successfully")
        return 0
    
    def _load_config(self) -> Dict[str, Any]:
        """Load deployment configuration."""
        config_file = Path('deployment_config.json')
        if config_file.exists():
            try:
                return json.loads(config_file.read_text())
            except json.JSONDecodeError as e:
                print(f"⚠️  Invalid config file: {e}")
        return {}
    
    def _deploy_cloudformation(self, atomic: AtomicDeployment, stack_name: str):
        """Deploy CloudFormation stack."""
        template_file = Path('cloudformation/main.yaml')
        if not template_file.exists():
            raise DeploymentError(f"Template not found: {template_file}")
        
        cmd = [
            'aws', 'cloudformation', 'deploy',
            '--template-file', str(template_file),
            '--stack-name', stack_name,
            '--capabilities', 'CAPABILITY_IAM',
            '--region', get_aws_region()
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if result.returncode != 0:
                raise DeploymentError(f"CloudFormation deployment failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise DeploymentError("CloudFormation deployment timed out")
        
        atomic.resources_created.append({
            'type': 'cloudformation',
            'name': stack_name
        })
    
    def status(self, args) -> int:
        """Check deployment status."""
        try:
            state = self.state_manager.load_state()
            if not state:
                print("❌ No deployment found")
                return 1
            
            stack_name = state.get('stack_name')
            if stack_name:
                try:
                    result = subprocess.run([
                        'aws', 'cloudformation', 'describe-stacks',
                        '--stack-name', stack_name,
                        '--region', get_aws_region()
                    ], capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        stack_info = json.loads(result.stdout)
                        status = stack_info['Stacks'][0]['StackStatus']
                        print(f"✅ Stack {stack_name}: {status}")
                        return 0
                except subprocess.TimeoutExpired:
                    print("⚠️  Status check timed out")
                    return 1
                except json.JSONDecodeError:
                    print("⚠️  Invalid response from AWS CLI")
                    return 1
            
            print("❌ Stack not found")
            return 1
        except Exception as e:
            print(f"❌ Status check failed: {e}")
            return 1
    
    def rollback(self, args) -> int:
        """Rollback deployment."""
        try:
            state = self.state_manager.load_state()
            if not state:
                print("❌ No deployment to rollback")
                return 1
            
            stack_name = state.get('stack_name')
            if stack_name:
                print(f"🔄 Rolling back stack {stack_name}...")
                try:
                    subprocess.run([
                        'aws', 'cloudformation', 'delete-stack',
                        '--stack-name', stack_name,
                        '--region', get_aws_region()
                    ], check=True, timeout=300)
                    
                    self.state_manager.clear_state()
                    print("✅ Rollback completed")
                    return 0
                except subprocess.TimeoutExpired:
                    print("⚠️  Rollback timed out")
                    return 1
            
            print("❌ No stack to rollback")
            return 1
        except Exception as e:
            print(f"❌ Rollback failed: {e}")
            return 1
