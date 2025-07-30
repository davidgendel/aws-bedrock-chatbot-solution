"""
Enhanced deployment state management for robust deployment tracking.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


class DeploymentStateManager:
    """Manages deployment state with enhanced tracking and recovery."""
    
    def __init__(self, state_file: str = ".deployment_state"):
        self.state_file = Path(state_file)
        self.backup_file = Path(f"{state_file}.backup")
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load deployment state from file."""
        default_state = {
            "version": "2.0",
            "deployment_id": self._generate_deployment_id(),
            "started_at": datetime.utcnow().isoformat(),
            "current_step": None,
            "completed_steps": [],
            "failed_steps": [],
            "step_details": {},
            "environment": {
                "python_available": True,
                "aws_configured": False,
                "cdk_available": False
            },
            "resources": {
                "created": [],
                "failed": []
            },
            "recovery_points": []
        }
        
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    loaded_state = json.load(f)
                
                # Migrate old state format if needed
                if loaded_state.get("version") != "2.0":
                    loaded_state = self._migrate_state(loaded_state, default_state)
                
                return loaded_state
            except Exception as e:
                print(f"Warning: Could not load state file: {e}")
                # Try backup file
                if self.backup_file.exists():
                    try:
                        with open(self.backup_file, 'r') as f:
                            return json.load(f)
                    except Exception:
                        pass
        
        return default_state
    
    def _migrate_state(self, old_state: Dict[str, Any], default_state: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate old state format to new format."""
        migrated = default_state.copy()
        
        # Preserve important fields from old state
        if "current_step" in old_state:
            migrated["current_step"] = old_state["current_step"]
        if "completed_steps" in old_state:
            migrated["completed_steps"] = old_state["completed_steps"]
        
        return migrated
    
    def _generate_deployment_id(self) -> str:
        """Generate unique deployment ID."""
        return f"deploy_{int(time.time())}"
    
    def _save_state(self) -> None:
        """Save current state to file with backup."""
        try:
            # Create backup of current state
            if self.state_file.exists():
                self.state_file.rename(self.backup_file)
            
            # Save new state
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            # Remove old backup if save was successful
            if self.backup_file.exists():
                self.backup_file.unlink()
                
        except Exception as e:
            print(f"Warning: Could not save state: {e}")
            # Restore backup if save failed
            if self.backup_file.exists():
                self.backup_file.rename(self.state_file)
    
    def start_step(self, step_name: str, description: str = "") -> None:
        """Start a new deployment step."""
        self.state["current_step"] = step_name
        self.state["step_details"][step_name] = {
            "started_at": datetime.utcnow().isoformat(),
            "description": description,
            "status": "in_progress",
            "substeps": [],
            "errors": []
        }
        self._save_state()
    
    def complete_step(self, step_name: str, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark a step as completed."""
        if step_name not in self.state["completed_steps"]:
            self.state["completed_steps"].append(step_name)
        
        if step_name in self.state["step_details"]:
            self.state["step_details"][step_name].update({
                "completed_at": datetime.utcnow().isoformat(),
                "status": "completed",
                "result": result or {}
            })
        
        # Clear current step if it matches
        if self.state["current_step"] == step_name:
            self.state["current_step"] = None
        
        self._save_state()
    
    def fail_step(self, step_name: str, error: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Mark a step as failed."""
        if step_name not in self.state["failed_steps"]:
            self.state["failed_steps"].append(step_name)
        
        if step_name in self.state["step_details"]:
            self.state["step_details"][step_name].update({
                "failed_at": datetime.utcnow().isoformat(),
                "status": "failed",
                "error": error,
                "error_details": details or {}
            })
            self.state["step_details"][step_name]["errors"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "error": error,
                "details": details
            })
        
        self._save_state()
    
    def add_substep(self, step_name: str, substep: str, status: str = "completed") -> None:
        """Add a substep to a step."""
        if step_name in self.state["step_details"]:
            self.state["step_details"][step_name]["substeps"].append({
                "name": substep,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            })
            self._save_state()
    
    def create_recovery_point(self, name: str, description: str = "") -> None:
        """Create a recovery point."""
        recovery_point = {
            "name": name,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "completed_steps": self.state["completed_steps"].copy(),
            "current_step": self.state["current_step"]
        }
        
        self.state["recovery_points"].append(recovery_point)
        self._save_state()
    
    def add_resource(self, resource_type: str, resource_id: str, status: str = "created") -> None:
        """Track a created resource."""
        resource = {
            "type": resource_type,
            "id": resource_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if status == "created":
            self.state["resources"]["created"].append(resource)
        elif status == "failed":
            self.state["resources"]["failed"].append(resource)
        
        self._save_state()
    
    def update_environment(self, key: str, value: Any) -> None:
        """Update environment information."""
        self.state["environment"][key] = value
        self._save_state()
    
    def is_step_completed(self, step_name: str) -> bool:
        """Check if a step is completed."""
        return step_name in self.state["completed_steps"]
    
    def is_step_failed(self, step_name: str) -> bool:
        """Check if a step has failed."""
        return step_name in self.state["failed_steps"]
    
    def get_step_status(self, step_name: str) -> Optional[str]:
        """Get the status of a step."""
        if step_name in self.state["step_details"]:
            return self.state["step_details"][step_name].get("status")
        return None
    
    def get_next_step(self, step_order: List[str]) -> Optional[str]:
        """Get the next step to execute based on completed steps."""
        for step in step_order:
            if not self.is_step_completed(step) and not self.is_step_failed(step):
                return step
        return None
    
    def get_failed_steps(self) -> List[str]:
        """Get list of failed steps."""
        return self.state["failed_steps"].copy()
    
    def get_completed_steps(self) -> List[str]:
        """Get list of completed steps."""
        return self.state["completed_steps"].copy()
    
    def get_recovery_points(self) -> List[Dict[str, Any]]:
        """Get available recovery points."""
        return self.state["recovery_points"].copy()
    
    def get_deployment_summary(self) -> Dict[str, Any]:
        """Get deployment summary."""
        total_steps = len(self.state["step_details"])
        completed_steps = len(self.state["completed_steps"])
        failed_steps = len(self.state["failed_steps"])
        
        return {
            "deployment_id": self.state["deployment_id"],
            "started_at": self.state["started_at"],
            "current_step": self.state["current_step"],
            "progress": {
                "total_steps": total_steps,
                "completed_steps": completed_steps,
                "failed_steps": failed_steps,
                "percentage": (completed_steps / total_steps * 100) if total_steps > 0 else 0
            },
            "resources_created": len(self.state["resources"]["created"]),
            "resources_failed": len(self.state["resources"]["failed"]),
            "recovery_points": len(self.state["recovery_points"])
        }
    
    def reset_failed_steps(self) -> None:
        """Reset failed steps for retry."""
        for step in self.state["failed_steps"]:
            if step in self.state["step_details"]:
                self.state["step_details"][step]["status"] = "pending"
        
        self.state["failed_steps"] = []
        self._save_state()
    
    def cleanup(self) -> None:
        """Clean up state files."""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
            if self.backup_file.exists():
                self.backup_file.unlink()
        except Exception as e:
            print(f"Warning: Could not clean up state files: {e}")
    
    def export_state(self, export_file: str) -> None:
        """Export current state to a file."""
        with open(export_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def import_state(self, import_file: str) -> None:
        """Import state from a file."""
        with open(import_file, 'r') as f:
            self.state = json.load(f)
        self._save_state()


# Convenience functions for use in deployment scripts
def get_state_manager() -> DeploymentStateManager:
    """Get the global state manager instance."""
    return DeploymentStateManager()


def with_state_tracking(step_name: str, description: str = ""):
    """Decorator for automatic state tracking."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            state_manager = get_state_manager()
            state_manager.start_step(step_name, description)
            
            try:
                result = func(*args, **kwargs)
                state_manager.complete_step(step_name, {"result": str(result)})
                return result
            except Exception as e:
                state_manager.fail_step(step_name, str(e), {"exception_type": type(e).__name__})
                raise
        
        return wrapper
    return decorator
