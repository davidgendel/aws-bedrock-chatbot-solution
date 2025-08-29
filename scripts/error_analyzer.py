#!/usr/bin/env python3
"""
Advanced error analyzer for RAG Chatbot deployment.
Analyzes logs, detects AWS-specific issues, and provides contextual solutions.
"""
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import platform

class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

class ErrorAnalyzer:
    def __init__(self, log_file: str = "deployment.log"):
        self.log_file = log_file
        self.os_type = platform.system().lower()
        
        # AWS error patterns and solutions
        self.aws_error_patterns = {
            # Authentication and Permissions
            "InvalidUserID.NotFound": {
                "type": "aws_user_not_found",
                "title": "AWS User Not Found",
                "description": "The AWS user specified in your credentials doesn't exist",
                "solutions": [
                    "Check your AWS Access Key ID is correct",
                    "Verify the user exists in AWS IAM console",
                    "Run 'aws configure' to update credentials"
                ]
            },
            "SignatureDoesNotMatch": {
                "type": "aws_signature_error",
                "title": "AWS Signature Error",
                "description": "Your AWS Secret Access Key is incorrect",
                "solutions": [
                    "Run 'aws configure' and enter the correct Secret Access Key",
                    "Check for extra spaces or characters in your key",
                    "Generate a new Access Key pair in AWS IAM console"
                ]
            },
            "AccessDenied": {
                "type": "aws_permissions",
                "title": "Insufficient AWS Permissions",
                "description": "Your AWS user doesn't have required permissions",
                "solutions": [
                    "Ask your AWS admin to attach 'AdministratorAccess' policy",
                    "Or attach these specific policies: IAM, CloudFormation, Lambda, S3, RDS, API Gateway",
                    "Check if your account has MFA requirements"
                ]
            },
            "TokenRefreshRequired": {
                "type": "aws_token_expired",
                "title": "AWS Session Token Expired",
                "description": "Your temporary AWS credentials have expired",
                "solutions": [
                    "If using AWS SSO, run 'aws sso login'",
                    "If using temporary credentials, refresh them",
                    "Consider using long-term Access Keys for deployment"
                ]
            },
            
            # Resource Limits and Quotas
            "LimitExceeded": {
                "type": "aws_quota_limit",
                "title": "AWS Service Limit Exceeded",
                "description": "You've hit an AWS service limit or quota",
                "solutions": [
                    "Check AWS Service Quotas console for current limits",
                    "Request a quota increase if needed",
                    "Try deploying in a different region",
                    "Clean up unused resources"
                ]
            },
            "InsufficientCapacity": {
                "type": "aws_capacity",
                "title": "Insufficient AWS Capacity",
                "description": "AWS doesn't have enough capacity in this region",
                "solutions": [
                    "Try again in a few minutes",
                    "Deploy to a different availability zone",
                    "Consider using a different instance type",
                    "Try a different AWS region"
                ]
            },
            
            # CDK Specific Errors
            "ValidationException.*Template format error": {
                "type": "cdk_template_error",
                "title": "CDK Template Error",
                "description": "There's an error in the CloudFormation template",
                "solutions": [
                    "Update AWS CDK to the latest version: npm install -g aws-cdk",
                    "Run 'cdk doctor' to check for issues",
                    "Try 'cdk bootstrap' if not already done",
                    "Check if your region supports all required services"
                ]
            },
            "is not authorized to perform.*on resource": {
                "type": "cdk_permissions",
                "title": "CDK Permission Error",
                "description": "CDK doesn't have permission to create/modify resources",
                "solutions": [
                    "Ensure your AWS user has CloudFormation permissions",
                    "Check if there are resource-based policies blocking access",
                    "Verify your account isn't in an organization with restrictive SCPs"
                ]
            },
            
            # Network and Connectivity
            "ConnectTimeoutError": {
                "type": "network_timeout",
                "title": "Network Connection Timeout",
                "description": "Cannot connect to AWS services",
                "solutions": [
                    "Check your internet connection",
                    "Verify firewall isn't blocking AWS endpoints",
                    "Try using a different network",
                    "Check if you're behind a corporate proxy"
                ]
            },
            "EndpointConnectionError": {
                "type": "network_endpoint",
                "title": "AWS Endpoint Connection Error",
                "description": "Cannot reach AWS service endpoints",
                "solutions": [
                    "Check if the AWS region is correct",
                    "Verify the service is available in your region",
                    "Check DNS resolution for AWS endpoints",
                    "Try using AWS CLI with --debug flag for more info"
                ]
            },
            
            # Service-Specific Errors
            "DBInstanceAlreadyExists": {
                "type": "rds_exists",
                "title": "Database Already Exists",
                "description": "An RDS instance with this name already exists",
                "solutions": [
                    "Choose a different database name in config.json",
                    "Delete the existing database if it's not needed",
                    "Use a different AWS region",
                    "Check if this is a leftover from a previous deployment"
                ]
            },
            "InvalidParameterValue.*not supported": {
                "type": "service_not_supported",
                "title": "Service Not Supported in Region",
                "description": "The requested service/feature isn't available in your region",
                "solutions": [
                    "Try a different AWS region (us-east-1 has most services)",
                    "Check AWS service availability by region",
                    "Use alternative services if available",
                    "Contact AWS support for service availability"
                ]
            }
        }
        
        # Python/System error patterns
        self.system_error_patterns = {
            "ModuleNotFoundError": {
                "type": "python_module_missing",
                "title": "Python Module Missing",
                "description": "Required Python package is not installed",
                "solutions": [
                    "Run 'pip3 install -r requirements.txt'",
                    "Check if you're in the correct directory",
                    "Verify Python virtual environment is activated",
                    "Try 'pip3 install --upgrade pip' first"
                ]
            },
            "Permission denied": {
                "type": "permission_denied",
                "title": "Permission Denied",
                "description": "Insufficient permissions to perform operation",
                "solutions": self._get_permission_solutions()
            },
            "command not found": {
                "type": "command_not_found",
                "title": "Command Not Found",
                "description": "Required command/tool is not installed or not in PATH",
                "solutions": self._get_command_solutions()
            }
        }
    
    def _get_permission_solutions(self) -> List[str]:
        """Get OS-specific permission solutions."""
        if self.os_type == "windows":
            return [
                "Run Command Prompt as Administrator",
                "Check file/folder permissions",
                "Ensure you have write access to the directory"
            ]
        else:
            return [
                "Try running with 'sudo' if appropriate",
                "Check file permissions with 'ls -la'",
                "Ensure you own the files: 'sudo chown -R $USER:$USER .'",
                "Make scripts executable: 'chmod +x chatbot'"
            ]
    
    def _get_command_solutions(self) -> List[str]:
        """Get OS-specific command installation solutions."""
        if self.os_type == "darwin":  # macOS
            return [
                "Install missing tools with Homebrew: 'brew install <tool>'",
                "Check if Xcode Command Line Tools are installed",
                "Update your PATH environment variable",
                "Restart your terminal after installation"
            ]
        elif self.os_type == "linux":
            return [
                "Install with package manager: 'sudo apt install <tool>' or 'sudo yum install <tool>'",
                "Check if the tool is in your PATH: 'which <command>'",
                "Update package lists: 'sudo apt update'",
                "Install build tools if needed: 'sudo apt install build-essential'"
            ]
        else:  # Windows
            return [
                "Install from official website or use package manager",
                "Add installation directory to PATH environment variable",
                "Restart Command Prompt after installation",
                "Consider using Windows Subsystem for Linux (WSL)"
            ]
    
    def analyze_log(self) -> Optional[Dict]:
        """Analyze deployment log for errors."""
        if not Path(self.log_file).exists():
            return None
        
        try:
            with open(self.log_file, 'r') as f:
                log_content = f.read()
            
            # Check for AWS errors first (more specific)
            for pattern, error_info in self.aws_error_patterns.items():
                if re.search(pattern, log_content, re.IGNORECASE | re.MULTILINE):
                    return self._create_error_response(error_info, log_content, pattern)
            
            # Check for system errors
            for pattern, error_info in self.system_error_patterns.items():
                if re.search(pattern, log_content, re.IGNORECASE):
                    return self._create_error_response(error_info, log_content, pattern)
            
            # If no specific pattern matches, try to extract generic error
            return self._extract_generic_error(log_content)
            
        except Exception as e:
            return {
                "type": "log_analysis_error",
                "title": "Log Analysis Error",
                "description": f"Could not analyze log file: {e}",
                "solutions": ["Check if log file exists and is readable"]
            }
    
    def _create_error_response(self, error_info: Dict, log_content: str, pattern: str) -> Dict:
        """Create detailed error response."""
        # Extract relevant log lines
        relevant_lines = self._extract_relevant_lines(log_content, pattern)
        
        return {
            "type": error_info["type"],
            "title": error_info["title"],
            "description": error_info["description"],
            "solutions": error_info["solutions"],
            "log_excerpt": relevant_lines,
            "pattern_matched": pattern
        }
    
    def _extract_relevant_lines(self, log_content: str, pattern: str) -> List[str]:
        """Extract relevant lines from log around the error."""
        lines = log_content.split('\n')
        relevant_lines = []
        
        for i, line in enumerate(lines):
            if re.search(pattern, line, re.IGNORECASE):
                # Include 2 lines before and after the error
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                relevant_lines.extend(lines[start:end])
                break
        
        return relevant_lines[:10]  # Limit to 10 lines
    
    def _extract_generic_error(self, log_content: str) -> Optional[Dict]:
        """Extract generic error information from log."""
        # Look for common error indicators
        error_indicators = [
            r"ERROR:.*",
            r"Error:.*",
            r"Exception:.*",
            r"Failed:.*",
            r"FAILED:.*"
        ]
        
        for pattern in error_indicators:
            matches = re.findall(pattern, log_content, re.IGNORECASE)
            if matches:
                return {
                    "type": "generic_error",
                    "title": "Deployment Error Detected",
                    "description": "An error was detected in the deployment log",
                    "solutions": [
                        "Check the log file for more details",
                        "Try running the deployment again",
                        "Contact support with the error details"
                    ],
                    "log_excerpt": matches[:5]  # First 5 matches
                }
        
        return None
    
    def check_environment(self) -> Dict:
        """Check environment for common issues."""
        issues = []
        
        # Check Python version
        try:
            result = subprocess.run(['python3', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split()[1]
                major, minor = map(int, version.split('.')[:2])
                if major < 3 or (major == 3 and minor < 9):
                    issues.append({
                        "type": "python_version",
                        "severity": "high",
                        "message": f"Python {version} is too old (need 3.9+)",
                        "solution": "Install Python 3.12+ from python.org"
                    })
        except FileNotFoundError:
            issues.append({
                "type": "python_missing",
                "severity": "critical",
                "message": "Python 3 is not installed",
                "solution": "Install Python 3 from python.org"
            })
        
        # Check AWS CLI
        try:
            result = subprocess.run(['aws', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                issues.append({
                    "type": "aws_cli_error",
                    "severity": "high",
                    "message": "AWS CLI is not working properly",
                    "solution": "Reinstall AWS CLI from aws.amazon.com/cli"
                })
        except FileNotFoundError:
            issues.append({
                "type": "aws_cli_missing",
                "severity": "critical",
                "message": "AWS CLI is not installed",
                "solution": "Install AWS CLI from aws.amazon.com/cli"
            })
        
        # Check AWS credentials
        try:
            result = subprocess.run(['aws', 'sts', 'get-caller-identity'], capture_output=True, text=True)
            if result.returncode != 0:
                issues.append({
                    "type": "aws_credentials",
                    "severity": "critical",
                    "message": "AWS credentials are not configured",
                    "solution": "Run 'aws configure' to set up credentials"
                })
        except Exception:
            pass
        
        # Check disk space
        try:
            import shutil
            free_space = shutil.disk_usage('.').free
            if free_space < 1024 * 1024 * 1024:  # Less than 1GB
                issues.append({
                    "type": "disk_space",
                    "severity": "medium",
                    "message": f"Low disk space: {free_space // (1024*1024)} MB available",
                    "solution": "Free up disk space before deployment"
                })
        except Exception:
            pass
        
        return {
            "issues": issues,
            "critical_count": len([i for i in issues if i["severity"] == "critical"]),
            "high_count": len([i for i in issues if i["severity"] == "high"]),
            "medium_count": len([i for i in issues if i["severity"] == "medium"])
        }
    
    def display_error_analysis(self, error_info: Dict):
        """Display formatted error analysis."""
        print(f"\n{Colors.RED}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.NC}")
        print(f"{Colors.RED}║ 🔍 Error Analysis Results{Colors.NC}")
        print(f"{Colors.RED}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.NC}")
        
        print(f"\n{Colors.YELLOW}❌ {error_info['title']}{Colors.NC}")
        print(f"{Colors.CYAN}📝 Description: {error_info['description']}{Colors.NC}")
        
        print(f"\n{Colors.GREEN}💡 Recommended Solutions:{Colors.NC}")
        for i, solution in enumerate(error_info['solutions'], 1):
            print(f"   {i}. {solution}")
        
        if error_info.get('log_excerpt'):
            print(f"\n{Colors.BLUE}📋 Relevant Log Lines:{Colors.NC}")
            for line in error_info['log_excerpt']:
                if line.strip():
                    print(f"   {line}")
    
    def display_environment_issues(self, env_check: Dict):
        """Display environment issues."""
        issues = env_check['issues']
        if not issues:
            print(f"{Colors.GREEN}✅ Environment check passed - no issues found{Colors.NC}")
            return
        
        print(f"\n{Colors.YELLOW}⚠️  Environment Issues Detected:{Colors.NC}")
        
        # Group by severity
        for severity in ['critical', 'high', 'medium']:
            severity_issues = [i for i in issues if i['severity'] == severity]
            if severity_issues:
                color = Colors.RED if severity == 'critical' else Colors.YELLOW if severity == 'high' else Colors.CYAN
                print(f"\n{color}{severity.upper()} Issues:{Colors.NC}")
                for issue in severity_issues:
                    print(f"   ❌ {issue['message']}")
                    print(f"      💡 {issue['solution']}")


def analyze_deployment_error(log_file: str = "deployment.log") -> bool:
    """Analyze deployment error and display results."""
    analyzer = ErrorAnalyzer(log_file)
    
    # Check environment first
    env_check = analyzer.check_environment()
    analyzer.display_environment_issues(env_check)
    
    # Analyze log if it exists
    error_info = analyzer.analyze_log()
    if error_info:
        analyzer.display_error_analysis(error_info)
        return True
    
    return False

if __name__ == "__main__":
    # Test the error analyzer
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        log_file = "deployment.log"
    
    found_error = analyze_deployment_error(log_file)
    if not found_error:
        print(f"{Colors.GREEN}✅ No specific errors detected in log file{Colors.NC}")
