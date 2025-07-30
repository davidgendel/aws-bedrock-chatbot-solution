#!/usr/bin/env python3
"""
Robust recovery manager for RAG Chatbot deployment.
Handles granular state tracking, rollback, and resource cleanup.
"""
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import ClientError

class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

class RecoveryManager:
    def __init__(self, state_file: str = ".deployment_recovery_state"):
        self.state_file = state_file
        self.backup_dir = Path(".deployment_backup")
        self.backup_dir.mkdir(exist_ok=True)
        
        self.state = self._load_state()
        
        # Define recovery points with granular sub-steps
        self.recovery_points = {
            "dependencies": {
                "substeps": [
                    "check_python",
                    "install_pip_packages", 
                    "install_nodejs",
                    "install_cdk"
                ],
                "rollback_actions": [
                    self._rollback_pip_packages,
                    self._rollback_nodejs,
                    self._rollback_cdk
                ]
            },
            "aws_check": {
                "substeps": [
                    "check_aws_cli",
                    "validate_credentials",
                    "test_permissions"
                ],
                "rollback_actions": []
            },
            "config": {
                "substeps": [
                    "backup_existing_config",
                    "run_setup_wizard",
                    "validate_config"
                ],
                "rollback_actions": [
                    self._rollback_config
                ]
            },
            "infrastructure": {
                "substeps": [
                    "cdk_bootstrap",
                    "cdk_deploy",
                    "configure_resources"
                ],
                "rollback_actions": [
                    self._rollback_infrastructure
                ]
            },
            "knowledge_base": {
                "substeps": [
                    "create_documents_folder",
                    "process_documents",
                    "upload_to_database"
                ],
                "rollback_actions": [
                    self._rollback_knowledge_base
                ]
            },
            "finalize": {
                "substeps": [
                    "run_validation",
                    "display_results"
                ],
                "rollback_actions": []
            }
        }
    
    def _load_state(self) -> Dict:
        """Load recovery state from file."""
        try:
            if Path(self.state_file).exists():
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load recovery state: {e}")
        
        return {
            "deployment_id": f"deploy_{int(time.time())}",
            "start_time": time.time(),
            "current_step": None,
            "current_substep": None,
            "completed_steps": [],
            "completed_substeps": {},
            "failed_steps": [],
            "aws_resources": {},
            "backups": {},
            "rollback_stack": []
        }
    
    def _save_state(self):
        """Save current recovery state."""
        try:
            self.state["last_update"] = time.time()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save recovery state: {e}")
    
    def start_step(self, step_name: str):
        """Start a new deployment step."""
        self.state["current_step"] = step_name
        self.state["current_substep"] = None
        
        if step_name not in self.state["completed_substeps"]:
            self.state["completed_substeps"][step_name] = []
        
        print(f"{Colors.BLUE}🔄 Starting step: {step_name}{Colors.NC}")
        self._save_state()
    
    def start_substep(self, substep_name: str):
        """Start a substep within the current step."""
        if not self.state["current_step"]:
            raise ValueError("No current step set")
        
        self.state["current_substep"] = substep_name
        print(f"{Colors.CYAN}   ⚙️  Starting substep: {substep_name}{Colors.NC}")
        self._save_state()
    
    def complete_substep(self, substep_name: str, metadata: Optional[Dict] = None):
        """Mark a substep as completed."""
        current_step = self.state["current_step"]
        if current_step and substep_name not in self.state["completed_substeps"][current_step]:
            self.state["completed_substeps"][current_step].append(substep_name)
            
            # Store metadata for rollback if needed
            if metadata:
                if "substep_metadata" not in self.state:
                    self.state["substep_metadata"] = {}
                if current_step not in self.state["substep_metadata"]:
                    self.state["substep_metadata"][current_step] = {}
                self.state["substep_metadata"][current_step][substep_name] = metadata
        
        print(f"{Colors.GREEN}   ✅ Completed substep: {substep_name}{Colors.NC}")
        self._save_state()
    
    def complete_step(self, step_name: str):
        """Mark a step as completed."""
        if step_name not in self.state["completed_steps"]:
            self.state["completed_steps"].append(step_name)
        
        self.state["current_step"] = None
        self.state["current_substep"] = None
        
        print(f"{Colors.GREEN}✅ Completed step: {step_name}{Colors.NC}")
        self._save_state()
    
    def fail_step(self, step_name: str, substep_name: Optional[str], error_msg: str):
        """Record a step failure."""
        failure_info = {
            "step": step_name,
            "substep": substep_name,
            "error": error_msg,
            "timestamp": time.time()
        }
        
        self.state["failed_steps"].append(failure_info)
        print(f"{Colors.RED}❌ Failed at {step_name}" + (f":{substep_name}" if substep_name else "") + f": {error_msg}{Colors.NC}")
        self._save_state()
    
    def track_aws_resource(self, resource_type: str, resource_id: str, metadata: Dict):
        """Track AWS resources for potential cleanup."""
        if resource_type not in self.state["aws_resources"]:
            self.state["aws_resources"][resource_type] = []
        
        resource_info = {
            "id": resource_id,
            "metadata": metadata,
            "created_at": time.time()
        }
        
        self.state["aws_resources"][resource_type].append(resource_info)
        self._save_state()
    
    def create_backup(self, file_path: str, backup_name: str):
        """Create backup of important files."""
        try:
            source = Path(file_path)
            if source.exists():
                backup_path = self.backup_dir / f"{backup_name}_{int(time.time())}"
                
                if source.is_file():
                    backup_path.write_text(source.read_text())
                else:
                    # For directories, create a simple backup
                    import shutil
                    shutil.copytree(source, backup_path)
                
                self.state["backups"][backup_name] = str(backup_path)
                self._save_state()
                
                print(f"{Colors.CYAN}💾 Created backup: {backup_name} -> {backup_path}{Colors.NC}")
                return str(backup_path)
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Could not create backup for {file_path}: {e}{Colors.NC}")
        
        return None
    
    def can_recover(self) -> bool:
        """Check if recovery is possible."""
        return (
            len(self.state.get("completed_steps", [])) > 0 or
            any(len(substeps) > 0 for substeps in self.state.get("completed_substeps", {}).values())
        )
    
    def get_recovery_point(self) -> Tuple[str, Optional[str]]:
        """Get the point from which recovery should start."""
        current_step = self.state.get("current_step")
        current_substep = self.state.get("current_substep")
        
        if current_step and current_substep:
            # Resume from current substep
            return current_step, current_substep
        elif current_step:
            # Resume from beginning of current step
            return current_step, None
        else:
            # Find last completed step
            completed_steps = self.state.get("completed_steps", [])
            if completed_steps:
                last_step = completed_steps[-1]
                step_names = list(self.recovery_points.keys())
                try:
                    next_index = step_names.index(last_step) + 1
                    if next_index < len(step_names):
                        return step_names[next_index], None
                except ValueError:
                    pass
            
            # Start from beginning
            return list(self.recovery_points.keys())[0], None
    
    def show_recovery_info(self):
        """Display recovery information."""
        if not self.can_recover():
            print(f"{Colors.YELLOW}ℹ️  No recovery information available{Colors.NC}")
            return
        
        step, substep = self.get_recovery_point()
        
        print(f"\n{Colors.BLUE}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.NC}")
        print(f"{Colors.BLUE}║ 🔄 Recovery Information{Colors.NC}")
        print(f"{Colors.BLUE}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.NC}")
        
        print(f"\n{Colors.CYAN}📊 Deployment Progress:{Colors.NC}")
        for step_name, step_info in self.recovery_points.items():
            if step_name in self.state.get("completed_steps", []):
                status = "✅ Completed"
            elif step_name == self.state.get("current_step"):
                completed_substeps = len(self.state.get("completed_substeps", {}).get(step_name, []))
                total_substeps = len(step_info["substeps"])
                status = f"🔄 In Progress ({completed_substeps}/{total_substeps})"
            else:
                status = "⏳ Pending"
            
            print(f"   {status} {step_name}")
        
        print(f"\n{Colors.GREEN}🎯 Recovery Point: {step}" + (f" -> {substep}" if substep else "") + f"{Colors.NC}")
        
        # Show failed steps if any
        failed_steps = self.state.get("failed_steps", [])
        if failed_steps:
            print(f"\n{Colors.RED}❌ Previous Failures:{Colors.NC}")
            for failure in failed_steps[-3:]:  # Show last 3 failures
                timestamp = datetime.fromtimestamp(failure["timestamp"]).strftime("%H:%M:%S")
                print(f"   [{timestamp}] {failure['step']}: {failure['error']}")
    
    def perform_rollback(self, target_step: Optional[str] = None) -> bool:
        """Perform rollback to a specific step or complete rollback."""
        print(f"\n{Colors.YELLOW}🔄 Starting rollback process...{Colors.NC}")
        
        try:
            # Determine rollback scope
            if target_step:
                steps_to_rollback = self._get_steps_to_rollback(target_step)
            else:
                steps_to_rollback = list(reversed(self.state.get("completed_steps", [])))
            
            success = True
            for step_name in steps_to_rollback:
                if not self._rollback_step(step_name):
                    success = False
                    break
            
            if success:
                print(f"{Colors.GREEN}✅ Rollback completed successfully{Colors.NC}")
                # Update state
                if target_step:
                    self.state["completed_steps"] = [s for s in self.state["completed_steps"] if s != target_step]
                else:
                    self.state["completed_steps"] = []
                    self.state["completed_substeps"] = {}
                self._save_state()
            else:
                print(f"{Colors.RED}❌ Rollback encountered errors{Colors.NC}")
            
            return success
            
        except Exception as e:
            print(f"{Colors.RED}❌ Rollback failed: {e}{Colors.NC}")
            return False
    
    def _get_steps_to_rollback(self, target_step: str) -> List[str]:
        """Get list of steps that need to be rolled back."""
        completed_steps = self.state.get("completed_steps", [])
        try:
            target_index = completed_steps.index(target_step)
            return list(reversed(completed_steps[target_index:]))
        except ValueError:
            return []
    
    def _rollback_step(self, step_name: str) -> bool:
        """Rollback a specific step."""
        print(f"{Colors.CYAN}🔄 Rolling back step: {step_name}{Colors.NC}")
        
        try:
            step_info = self.recovery_points.get(step_name, {})
            rollback_actions = step_info.get("rollback_actions", [])
            
            for action in rollback_actions:
                if not action(step_name):
                    return False
            
            print(f"{Colors.GREEN}✅ Rolled back step: {step_name}{Colors.NC}")
            return True
            
        except Exception as e:
            print(f"{Colors.RED}❌ Error rolling back {step_name}: {e}{Colors.NC}")
            return False
    
    def _rollback_pip_packages(self, step_name: str) -> bool:
        """Rollback pip package installations."""
        try:
            # This is tricky - we can't easily uninstall packages that were installed
            # Instead, we'll just note that manual cleanup might be needed
            print(f"{Colors.YELLOW}⚠️  Note: Installed Python packages may need manual cleanup{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Error in pip rollback: {e}{Colors.NC}")
            return False
    
    def _rollback_nodejs(self, step_name: str) -> bool:
        """Rollback Node.js installation."""
        try:
            # Node.js rollback is complex and system-dependent
            print(f"{Colors.YELLOW}⚠️  Note: Node.js installation may need manual cleanup{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Error in Node.js rollback: {e}{Colors.NC}")
            return False
    
    def _rollback_cdk(self, step_name: str) -> bool:
        """Rollback CDK installation."""
        try:
            # Try to uninstall CDK
            result = subprocess.run(['npm', 'uninstall', '-g', 'aws-cdk'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ Uninstalled AWS CDK{Colors.NC}")
            else:
                print(f"{Colors.YELLOW}⚠️  Could not uninstall CDK automatically{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Error in CDK rollback: {e}{Colors.NC}")
            return False
    
    def _rollback_config(self, step_name: str) -> bool:
        """Rollback configuration changes."""
        try:
            # Restore config from backup
            backup_path = self.state.get("backups", {}).get("config.json")
            if backup_path and Path(backup_path).exists():
                Path("config.json").write_text(Path(backup_path).read_text())
                print(f"{Colors.GREEN}✅ Restored config.json from backup{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Error in config rollback: {e}{Colors.NC}")
            return False
    
    def _rollback_infrastructure(self, step_name: str) -> bool:
        """Rollback AWS infrastructure."""
        try:
            # Try to destroy CDK stack
            print(f"{Colors.CYAN}🔄 Attempting to destroy AWS infrastructure...{Colors.NC}")
            
            result = subprocess.run(['cdk', 'destroy', '--force'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ AWS infrastructure destroyed{Colors.NC}")
            else:
                print(f"{Colors.YELLOW}⚠️  Could not destroy infrastructure automatically{Colors.NC}")
                print(f"   You may need to manually delete the CloudFormation stack")
            
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Error in infrastructure rollback: {e}{Colors.NC}")
            return False
    
    def _rollback_knowledge_base(self, step_name: str) -> bool:
        """Rollback knowledge base setup."""
        try:
            # Remove documents folder if it was created
            docs_folder = Path("documents")
            if docs_folder.exists() and docs_folder.is_dir():
                import shutil
                shutil.rmtree(docs_folder)
                print(f"{Colors.GREEN}✅ Removed documents folder{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Error in knowledge base rollback: {e}{Colors.NC}")
            return False
    
    def cleanup_failed_resources(self):
        """Clean up AWS resources from failed deployment."""
        print(f"\n{Colors.CYAN}🧹 Cleaning up failed AWS resources...{Colors.NC}")
        
        aws_resources = self.state.get("aws_resources", {})
        if not aws_resources:
            print(f"{Colors.GREEN}✅ No AWS resources to clean up{Colors.NC}")
            return
        
        # This would need to be implemented based on specific resource types
        # For now, we'll just report what resources were tracked
        for resource_type, resources in aws_resources.items():
            print(f"{Colors.YELLOW}⚠️  Found {len(resources)} {resource_type} resources{Colors.NC}")
            for resource in resources:
                print(f"   - {resource['id']}")
        
        print(f"{Colors.YELLOW}⚠️  Manual cleanup may be required for tracked resources{Colors.NC}")
    
    def cleanup(self):
        """Clean up recovery files."""
        try:
            if Path(self.state_file).exists():
                Path(self.state_file).unlink()
            
            # Optionally clean up backup directory
            # import shutil
            # if self.backup_dir.exists():
            #     shutil.rmtree(self.backup_dir)
            
            print(f"{Colors.GREEN}✅ Recovery state cleaned up{Colors.NC}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Could not clean up recovery state: {e}{Colors.NC}")


def show_recovery_options():
    """Show available recovery options."""
    recovery_manager = RecoveryManager()
    
    if not recovery_manager.can_recover():
        print(f"{Colors.YELLOW}ℹ️  No recovery information available{Colors.NC}")
        return False
    
    recovery_manager.show_recovery_info()
    
    print(f"\n{Colors.CYAN}🔧 Recovery Options:{Colors.NC}")
    print(f"   1. Resume deployment from last point")
    print(f"   2. Rollback and start fresh")
    print(f"   3. Rollback to specific step")
    print(f"   4. Clean up failed resources")
    
    return True

if __name__ == "__main__":
    # Test recovery manager
    recovery_manager = RecoveryManager()
    show_recovery_options()
