#!/usr/bin/env python3
"""
Enhanced progress tracking system for RAG Chatbot deployment.
Provides real-time progress updates, time estimates, and sub-task tracking.
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading
import sys

class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

class ProgressTracker:
    def __init__(self, state_file: str = ".deployment_state_enhanced"):
        self.state_file = state_file
        self.state = self._load_state()
        self.start_time = time.time()
        self.current_step = 0
        self.current_subtask = 0
        self.spinner_active = False
        self.spinner_thread = None
        
        # Historical timing data for estimates (in seconds)
        self.step_estimates = {
            "dependencies": {"base": 120, "subtasks": [30, 45, 30, 15]},  # 2 min total
            "aws_check": {"base": 30, "subtasks": [10, 15, 5]},           # 30 sec total
            "config": {"base": 60, "subtasks": [20, 25, 15]},             # 1 min total
            "infrastructure": {"base": 600, "subtasks": [60, 480, 60]},   # 10 min total
            "knowledge_base": {"base": 90, "subtasks": [30, 45, 15]},     # 1.5 min total
            "finalize": {"base": 45, "subtasks": [30, 15]}                # 45 sec total
        }
        
        self.step_names = [
            "dependencies", "aws_check", "config", 
            "infrastructure", "knowledge_base", "finalize"
        ]
        
        self.step_descriptions = {
            "dependencies": "Installing dependencies",
            "aws_check": "Checking AWS setup",
            "config": "Setting up configuration",
            "infrastructure": "Deploying to AWS",
            "knowledge_base": "Setting up knowledge base",
            "finalize": "Finalizing setup"
        }
        
        self.subtask_descriptions = {
            "dependencies": ["Checking Python", "Installing packages", "Installing Node.js", "Installing CDK"],
            "aws_check": ["Checking AWS CLI", "Validating credentials", "Testing permissions"],
            "config": ["Loading configuration", "Running setup wizard", "Validating config"],
            "infrastructure": ["Preparing CDK", "Deploying infrastructure", "Configuring resources"],
            "knowledge_base": ["Creating documents folder", "Processing documents", "Uploading to database"],
            "finalize": ["Running validation", "Displaying results"]
        }
    
    def _load_state(self) -> Dict:
        """Load deployment state from file."""
        try:
            if Path(self.state_file).exists():
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        
        return {
            "current_step": 0,
            "current_subtask": 0,
            "completed_steps": [],
            "failed_steps": [],
            "start_time": time.time(),
            "step_times": {}
        }
    
    def _save_state(self):
        """Save current state to file."""
        try:
            self.state.update({
                "current_step": self.current_step,
                "current_subtask": self.current_subtask,
                "last_update": time.time()
            })
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save progress state: {e}")
    
    def start_step(self, step_name: str):
        """Start a new deployment step."""
        self.current_step = self.step_names.index(step_name)
        self.current_subtask = 0
        self.state["step_times"][step_name] = {"start": time.time()}
        self._save_state()
        
        # Calculate remaining time
        remaining_time = self._calculate_remaining_time()
        
        print(f"\n{Colors.BLUE}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.NC}")
        print(f"{Colors.BLUE}║ Step {self.current_step + 1}/6: {self.step_descriptions[step_name]:<60} ║{Colors.NC}")
        print(f"{Colors.BLUE}║ Estimated time remaining: {remaining_time:<46} ║{Colors.NC}")
        print(f"{Colors.BLUE}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.NC}")
    
    def update_subtask(self, subtask_index: int, message: str = ""):
        """Update current subtask progress."""
        self.current_subtask = subtask_index
        step_name = self.step_names[self.current_step]
        
        if subtask_index < len(self.subtask_descriptions[step_name]):
            subtask_desc = self.subtask_descriptions[step_name][subtask_index]
            if message:
                subtask_desc = f"{subtask_desc}: {message}"
        else:
            subtask_desc = message or "Processing..."
        
        # Calculate progress
        total_subtasks = len(self.subtask_descriptions[step_name])
        subtask_progress = (subtask_index + 1) / total_subtasks
        overall_progress = (self.current_step + subtask_progress) / len(self.step_names)
        
        # Create progress bar
        bar_width = 50
        filled = int(bar_width * overall_progress)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        # Calculate time info
        elapsed = time.time() - self.start_time
        remaining = self._calculate_remaining_time()
        
        print(f"\r{Colors.CYAN}🚀 [{bar}] {overall_progress*100:.1f}% | {subtask_desc:<40} | ETA: {remaining}{Colors.NC}", end="", flush=True)
        
        self._save_state()
    
    def complete_step(self, step_name: str):
        """Mark a step as completed."""
        self.state["completed_steps"].append(step_name)
        self.state["step_times"][step_name]["end"] = time.time()
        
        duration = self.state["step_times"][step_name]["end"] - self.state["step_times"][step_name]["start"]
        print(f"\n{Colors.GREEN}✅ {self.step_descriptions[step_name]} completed in {self._format_duration(duration)}{Colors.NC}")
        
        self._save_state()
    
    def fail_step(self, step_name: str, error_msg: str):
        """Mark a step as failed."""
        self.state["failed_steps"].append({
            "step": step_name,
            "error": error_msg,
            "time": time.time()
        })
        self.state["step_times"][step_name]["end"] = time.time()
        self._save_state()
    
    def start_spinner(self, message: str):
        """Start animated spinner for long operations."""
        self.spinner_active = True
        self.spinner_thread = threading.Thread(target=self._spinner_animation, args=(message,))
        self.spinner_thread.daemon = True
        self.spinner_thread.start()
    
    def stop_spinner(self):
        """Stop animated spinner."""
        self.spinner_active = False
        if self.spinner_thread:
            self.spinner_thread.join(timeout=1)
        print("\r" + " " * 80 + "\r", end="", flush=True)  # Clear spinner line
    
    def _spinner_animation(self, message: str):
        """Animated spinner for long operations."""
        spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        while self.spinner_active:
            print(f"\r{Colors.YELLOW}{spinner_chars[i]} {message}...{Colors.NC}", end="", flush=True)
            i = (i + 1) % len(spinner_chars)
            time.sleep(0.1)
    
    def _calculate_remaining_time(self) -> str:
        """Calculate estimated remaining time."""
        elapsed = time.time() - self.start_time
        
        # Calculate total estimated time
        total_estimate = sum(step["base"] for step in self.step_estimates.values())
        
        # Calculate completed time estimate
        completed_estimate = 0
        for i, step_name in enumerate(self.step_names):
            if i < self.current_step:
                completed_estimate += self.step_estimates[step_name]["base"]
            elif i == self.current_step:
                # Add partial completion of current step
                subtasks = self.step_estimates[step_name]["subtasks"]
                if self.current_subtask < len(subtasks):
                    completed_estimate += sum(subtasks[:self.current_subtask])
        
        # Estimate remaining time
        remaining_estimate = total_estimate - completed_estimate
        
        # Adjust based on actual vs estimated time so far
        if completed_estimate > 0:
            time_factor = elapsed / completed_estimate
            remaining_estimate *= time_factor
        
        return self._format_duration(remaining_estimate)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def show_summary(self):
        """Show deployment summary."""
        total_time = time.time() - self.start_time
        
        print(f"\n{Colors.GREEN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.NC}")
        print(f"{Colors.GREEN}║ 🎉 Deployment Summary{Colors.NC}")
        print(f"{Colors.GREEN}╠══════════════════════════════════════════════════════════════════════════════╣{Colors.NC}")
        print(f"{Colors.GREEN}║ Total time: {self._format_duration(total_time):<63} ║{Colors.NC}")
        print(f"{Colors.GREEN}║ Steps completed: {len(self.state['completed_steps'])}/6{Colors.NC}")
        
        if self.state.get("failed_steps"):
            print(f"{Colors.YELLOW}║ Failed steps: {len(self.state['failed_steps']):<59} ║{Colors.NC}")
        
        print(f"{Colors.GREEN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.NC}")
        
        # Show step breakdown
        print(f"\n{Colors.CYAN}📊 Step Breakdown:{Colors.NC}")
        for step_name in self.step_names:
            if step_name in self.state["step_times"] and "end" in self.state["step_times"][step_name]:
                duration = self.state["step_times"][step_name]["end"] - self.state["step_times"][step_name]["start"]
                status = "✅" if step_name in self.state["completed_steps"] else "❌"
                print(f"   {status} {self.step_descriptions[step_name]}: {self._format_duration(duration)}")
    
    def cleanup(self):
        """Clean up progress tracking files."""
        try:
            if Path(self.state_file).exists():
                Path(self.state_file).unlink()
        except Exception:
            pass
    
    def can_recover(self) -> bool:
        """Check if deployment can be recovered."""
        return len(self.state.get("completed_steps", [])) > 0
    
    def get_recovery_point(self) -> Tuple[str, int]:
        """Get the point from which deployment can be recovered."""
        completed = self.state.get("completed_steps", [])
        if not completed:
            return self.step_names[0], 0
        
        last_completed = completed[-1]
        last_index = self.step_names.index(last_completed)
        
        if last_index + 1 < len(self.step_names):
            return self.step_names[last_index + 1], last_index + 1
        else:
            return self.step_names[-1], len(self.step_names) - 1


# Example usage functions for integration with deploy.sh
def create_progress_tracker():
    """Create and return a progress tracker instance."""
    return ProgressTracker()

def show_recovery_info():
    """Show recovery information if available."""
    tracker = ProgressTracker()
    if tracker.can_recover():
        step, index = tracker.get_recovery_point()
        print(f"{Colors.CYAN}🔄 Recovery available from step {index + 1}: {tracker.step_descriptions[step]}{Colors.NC}")
        return True
    return False

if __name__ == "__main__":
    # Test the progress tracker
    tracker = ProgressTracker()
    
    # Simulate deployment steps
    for step_name in tracker.step_names:
        tracker.start_step(step_name)
        subtasks = tracker.subtask_descriptions[step_name]
        
        for i, subtask in enumerate(subtasks):
            tracker.update_subtask(i, f"Working on {subtask}")
            time.sleep(1)  # Simulate work
        
        tracker.complete_step(step_name)
    
    tracker.show_summary()
    tracker.cleanup()
