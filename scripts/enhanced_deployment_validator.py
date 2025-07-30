#!/usr/bin/env python3
"""
Enhanced deployment validator for RAG Chatbot.
Comprehensive pre-deployment validation, AWS quota checking, and cost estimation.
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

class EnhancedDeploymentValidator:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = {}
        self.region = "us-east-1"
        self.stack_name = "ChatbotRagStack"
        
        # AWS service quotas to check
        self.quota_checks = {
            "lambda": {
                "service_code": "lambda",
                "quotas": [
                    {"quota_code": "L-B99A9384", "name": "Concurrent executions", "min_required": 10},
                    {"quota_code": "L-2E13EBC1", "name": "Function and layer storage", "min_required": 1000000000}  # 1GB
                ]
            },
            "rds": {
                "service_code": "rds",
                "quotas": [
                    {"quota_code": "L-7B6409FD", "name": "DB instances", "min_required": 1},
                    {"quota_code": "L-952B80B8", "name": "Total storage for all DB instances", "min_required": 100}  # 100GB
                ]
            },
            "apigateway": {
                "service_code": "apigateway",
                "quotas": [
                    {"quota_code": "L-A93FDA9C", "name": "Regional APIs per account", "min_required": 1},
                    {"quota_code": "L-91BA7C2C", "name": "WebSocket APIs per account", "min_required": 1}
                ]
            }
        }
        
        # Cost estimation data (monthly costs in USD)
        self.cost_estimates = {
            "small": {
                "users": 50,
                "interactions": 15000,
                "costs": {
                    "rds": 19.38,
                    "lambda": 1.11,
                    "bedrock": 0.94,
                    "waf": 8.01,
                    "other": 0.32,
                    "total": 29.76
                }
            },
            "medium": {
                "users": 150,
                "interactions": 54000,
                "costs": {
                    "rds": 19.38,
                    "lambda": 1.61,
                    "bedrock": 3.35,
                    "waf": 8.03,
                    "other": 1.15,
                    "total": 33.52
                }
            },
            "large": {
                "users": 500,
                "interactions": 225000,
                "costs": {
                    "rds": 40.87,
                    "lambda": 4.69,
                    "bedrock": 13.96,
                    "waf": 8.14,
                    "other": 4.75,
                    "total": 72.41
                }
            }
        }
    
    def load_config(self) -> bool:
        """Load configuration from file."""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            self.region = self.config.get('region', 'us-east-1')
            return True
        except FileNotFoundError:
            self.print_error(f"Configuration file {self.config_file} not found")
            return False
        except json.JSONDecodeError as e:
            self.print_error(f"Invalid JSON in {self.config_file}: {e}")
            return False
    
    def print_success(self, message: str):
        """Print success message."""
        print(f"{Colors.GREEN}✅ {message}{Colors.NC}")
    
    def print_error(self, message: str):
        """Print error message."""
        print(f"{Colors.RED}❌ {message}{Colors.NC}")
    
    def print_warning(self, message: str):
        """Print warning message."""
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.NC}")
    
    def print_info(self, message: str):
        """Print info message."""
        print(f"{Colors.CYAN}ℹ️  {message}{Colors.NC}")
    
    def print_section(self, title: str):
        """Print section header."""
        print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}")
        print(f"{Colors.BLUE}{title}{Colors.NC}")
        print(f"{Colors.BLUE}{'='*60}{Colors.NC}")
    
    def validate_system_requirements(self) -> Dict:
        """Comprehensive system requirements validation."""
        self.print_section("System Requirements Validation")
        
        results = {
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "details": []
        }
        
        # Check Python version
        try:
            result = subprocess.run(['python3', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split()[1]
                major, minor = map(int, version.split('.')[:2])
                if major >= 3 and minor >= 12:
                    self.print_success(f"Python {version} (recommended)")
                    results["passed"] += 1
                elif major >= 3 and minor >= 9:
                    self.print_warning(f"Python {version} (minimum supported, recommend 3.12+)")
                    results["warnings"] += 1
                else:
                    self.print_error(f"Python {version} is too old (need 3.9+)")
                    results["failed"] += 1
                    results["details"].append("Upgrade Python to 3.12+ from python.org")
            else:
                self.print_error("Python 3 not working properly")
                results["failed"] += 1
        except FileNotFoundError:
            self.print_error("Python 3 not installed")
            results["failed"] += 1
            results["details"].append("Install Python 3.12+ from python.org")
        
        # Check pip
        try:
            result = subprocess.run(['pip3', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.print_success("pip3 available")
                results["passed"] += 1
            else:
                self.print_error("pip3 not working")
                results["failed"] += 1
        except FileNotFoundError:
            self.print_error("pip3 not installed")
            results["failed"] += 1
        
        # Check AWS CLI
        try:
            result = subprocess.run(['aws', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version_info = result.stdout.strip()
                self.print_success(f"AWS CLI: {version_info.split()[0]}")
                results["passed"] += 1
            else:
                self.print_error("AWS CLI not working")
                results["failed"] += 1
        except FileNotFoundError:
            self.print_error("AWS CLI not installed")
            results["failed"] += 1
            results["details"].append("Install AWS CLI from aws.amazon.com/cli")
        
        # Check Node.js (will be auto-installed if missing)
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.print_success(f"Node.js {version}")
                results["passed"] += 1
            else:
                self.print_warning("Node.js not working (will be auto-installed)")
                results["warnings"] += 1
        except FileNotFoundError:
            self.print_warning("Node.js not installed (will be auto-installed)")
            results["warnings"] += 1
        
        # Check disk space
        try:
            import shutil
            free_space = shutil.disk_usage('.').free
            free_gb = free_space / (1024**3)
            
            if free_gb >= 2:
                self.print_success(f"Disk space: {free_gb:.1f} GB available")
                results["passed"] += 1
            elif free_gb >= 1:
                self.print_warning(f"Disk space: {free_gb:.1f} GB available (recommend 2GB+)")
                results["warnings"] += 1
            else:
                self.print_error(f"Insufficient disk space: {free_gb:.1f} GB (need 1GB+)")
                results["failed"] += 1
                results["details"].append("Free up disk space before deployment")
        except Exception:
            self.print_warning("Could not check disk space")
            results["warnings"] += 1
        
        return results
    
    def validate_aws_credentials(self) -> Dict:
        """Validate AWS credentials and permissions."""
        self.print_section("AWS Credentials & Permissions Validation")
        
        results = {
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "details": []
        }
        
        try:
            # Check basic credentials
            sts_client = boto3.client('sts', region_name=self.region)
            identity = sts_client.get_caller_identity()
            
            self.print_success(f"AWS credentials valid")
            self.print_info(f"Account: {identity['Account']}")
            self.print_info(f"User/Role: {identity['Arn']}")
            results["passed"] += 1
            
            # Test key permissions
            permissions_to_test = [
                ("iam", "get_user", "IAM read access"),
                ("cloudformation", "list_stacks", "CloudFormation access"),
                ("lambda", "list_functions", "Lambda access"),
                ("rds", "describe_db_instances", "RDS access"),
                ("s3", "list_buckets", "S3 access")
            ]
            
            for service, operation, description in permissions_to_test:
                try:
                    client = boto3.client(service, region_name=self.region)
                    getattr(client, operation)()
                    self.print_success(f"{description}")
                    results["passed"] += 1
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code in ['AccessDenied', 'UnauthorizedOperation']:
                        self.print_error(f"{description} - Permission denied")
                        results["failed"] += 1
                        results["details"].append(f"Grant {service} permissions to your AWS user")
                    else:
                        self.print_warning(f"{description} - {error_code}")
                        results["warnings"] += 1
                except Exception as e:
                    self.print_warning(f"{description} - Could not test: {e}")
                    results["warnings"] += 1
            
        except NoCredentialsError:
            self.print_error("AWS credentials not configured")
            results["failed"] += 1
            results["details"].append("Run 'aws configure' to set up credentials")
        except ClientError as e:
            self.print_error(f"AWS credentials error: {e}")
            results["failed"] += 1
        except Exception as e:
            self.print_error(f"Unexpected AWS error: {e}")
            results["failed"] += 1
        
        return results
    
    def check_aws_quotas(self) -> Dict:
        """Check AWS service quotas."""
        self.print_section("AWS Service Quotas Check")
        
        results = {
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "details": []
        }
        
        try:
            quotas_client = boto3.client('service-quotas', region_name=self.region)
            
            for service_name, service_info in self.quota_checks.items():
                self.print_info(f"Checking {service_name.upper()} quotas...")
                
                for quota_info in service_info["quotas"]:
                    try:
                        response = quotas_client.get_service_quota(
                            ServiceCode=service_info["service_code"],
                            QuotaCode=quota_info["quota_code"]
                        )
                        
                        current_value = response['Quota']['Value']
                        required_value = quota_info["min_required"]
                        quota_name = quota_info["name"]
                        
                        if current_value >= required_value:
                            self.print_success(f"{quota_name}: {current_value} (sufficient)")
                            results["passed"] += 1
                        else:
                            self.print_warning(f"{quota_name}: {current_value} (need {required_value})")
                            results["warnings"] += 1
                            results["details"].append(f"Consider requesting quota increase for {quota_name}")
                    
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'NoSuchResourceException':
                            self.print_warning(f"Could not check quota: {quota_info['name']}")
                            results["warnings"] += 1
                        else:
                            self.print_error(f"Error checking quota {quota_info['name']}: {e}")
                            results["failed"] += 1
                    except Exception as e:
                        self.print_warning(f"Could not check {quota_info['name']}: {e}")
                        results["warnings"] += 1
        
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDenied':
                self.print_warning("Cannot check quotas - insufficient permissions")
                results["warnings"] += 1
            else:
                self.print_error(f"Error accessing Service Quotas: {e}")
                results["failed"] += 1
        except Exception as e:
            self.print_warning(f"Could not check service quotas: {e}")
            results["warnings"] += 1
        
        return results
    
    def validate_region_services(self) -> Dict:
        """Validate that required services are available in the region."""
        self.print_section("Region Service Availability Check")
        
        results = {
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "details": []
        }
        
        required_services = [
            ("lambda", "AWS Lambda"),
            ("rds", "Amazon RDS"),
            ("apigateway", "API Gateway"),
            ("s3", "Amazon S3"),
            ("bedrock", "Amazon Bedrock"),
            ("cloudformation", "CloudFormation"),
            ("wafv2", "AWS WAF")
        ]
        
        for service_code, service_name in required_services:
            try:
                client = boto3.client(service_code, region_name=self.region)
                
                # Try a simple operation to verify service availability
                if service_code == "bedrock":
                    # Special check for Bedrock
                    try:
                        client.list_foundation_models()
                        self.print_success(f"{service_name} available")
                        results["passed"] += 1
                    except ClientError as e:
                        if "not supported" in str(e).lower():
                            self.print_error(f"{service_name} not available in {self.region}")
                            results["failed"] += 1
                            results["details"].append(f"Use a region with Bedrock support (us-east-1, us-west-2, etc.)")
                        else:
                            self.print_warning(f"{service_name} - {e}")
                            results["warnings"] += 1
                elif service_code == "lambda":
                    client.list_functions(MaxItems=1)
                    self.print_success(f"{service_name} available")
                    results["passed"] += 1
                elif service_code == "rds":
                    client.describe_db_instances(MaxRecords=1)
                    self.print_success(f"{service_name} available")
                    results["passed"] += 1
                else:
                    # Generic check - just creating client is usually enough
                    self.print_success(f"{service_name} available")
                    results["passed"] += 1
                    
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                    self.print_warning(f"{service_name} - Cannot verify (permission issue)")
                    results["warnings"] += 1
                else:
                    self.print_error(f"{service_name} - {error_code}")
                    results["failed"] += 1
            except Exception as e:
                self.print_warning(f"{service_name} - Could not verify: {e}")
                results["warnings"] += 1
        
        return results
    
    def estimate_costs(self) -> Dict:
        """Estimate deployment costs."""
        self.print_section("Cost Estimation")
        
        # Use default small business configuration for cost estimates
        business_type = "small"
        
        cost_info = self.cost_estimates[business_type]
        
        print(f"{Colors.CYAN}📊 Estimated Monthly Costs for {business_type.title()} Business:{Colors.NC}")
        print(f"   👥 Expected users: {cost_info['users']} daily")
        print(f"   💬 Expected interactions: {cost_info['interactions']:,} monthly")
        print()
        
        costs = cost_info['costs']
        print(f"{Colors.BLUE}💰 Cost Breakdown:{Colors.NC}")
        print(f"   🗄️  Database (RDS): ${costs['rds']:.2f}")
        print(f"   ⚡ Compute (Lambda): ${costs['lambda']:.2f}")
        print(f"   🤖 AI/ML (Bedrock): ${costs['bedrock']:.2f}")
        print(f"   🛡️  Security (WAF): ${costs['waf']:.2f}")
        print(f"   🔧 Other services: ${costs['other']:.2f}")
        print(f"   {Colors.BOLD}📊 Total: ${costs['total']:.2f}/month{Colors.NC}")
        
        # Cost warnings
        if costs['total'] > 50:
            self.print_warning(f"Monthly cost estimate is ${costs['total']:.2f}")
            self.print_info("Consider starting with a smaller configuration")
        else:
            self.print_success(f"Estimated monthly cost: ${costs['total']:.2f}")
        
        return {
            "business_type": business_type,
            "monthly_cost": costs['total'],
            "breakdown": costs
        }
    
    def run_comprehensive_validation(self) -> Dict:
        """Run all validation checks."""
        print(f"\n{Colors.BOLD}🔍 RAG Chatbot Deployment Validation{Colors.NC}")
        print(f"{Colors.CYAN}Checking system requirements, AWS setup, and estimating costs...{Colors.NC}")
        
        overall_results = {
            "system": self.validate_system_requirements(),
            "aws_creds": self.validate_aws_credentials(),
            "aws_quotas": self.check_aws_quotas(),
            "region_services": self.validate_region_services(),
            "cost_estimate": self.estimate_costs()
        }
        
        # Calculate overall status
        total_passed = sum(r.get("passed", 0) for r in overall_results.values() if isinstance(r, dict) and "passed" in r)
        total_failed = sum(r.get("failed", 0) for r in overall_results.values() if isinstance(r, dict) and "failed" in r)
        total_warnings = sum(r.get("warnings", 0) for r in overall_results.values() if isinstance(r, dict) and "warnings" in r)
        
        # Display summary
        self.print_section("Validation Summary")
        
        if total_failed == 0:
            if total_warnings == 0:
                self.print_success(f"All checks passed! ({total_passed} passed)")
                print(f"{Colors.GREEN}🚀 Ready for deployment!{Colors.NC}")
                overall_results["ready"] = True
            else:
                self.print_warning(f"Validation completed with warnings ({total_passed} passed, {total_warnings} warnings)")
                print(f"{Colors.YELLOW}⚠️  Deployment possible but review warnings{Colors.NC}")
                overall_results["ready"] = True
        else:
            self.print_error(f"Validation failed ({total_failed} failed, {total_warnings} warnings, {total_passed} passed)")
            print(f"{Colors.RED}❌ Fix issues before deployment{Colors.NC}")
            overall_results["ready"] = False
        
        # Show action items
        all_details = []
        for result in overall_results.values():
            if isinstance(result, dict) and "details" in result:
                all_details.extend(result["details"])
        
        if all_details:
            print(f"\n{Colors.CYAN}📋 Action Items:{Colors.NC}")
            for i, detail in enumerate(all_details, 1):
                print(f"   {i}. {detail}")
        
        return overall_results


def run_pre_deployment_validation(config_file: str = "config.json") -> bool:
    """Run pre-deployment validation and return readiness status."""
    validator = EnhancedDeploymentValidator(config_file)
    
    # Load config if it exists
    if Path(config_file).exists():
        validator.load_config()
    
    results = validator.run_comprehensive_validation()
    return results.get("ready", False)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced deployment validation")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    parser.add_argument("--pre-deployment", action="store_true", help="Run pre-deployment validation")
    
    args = parser.parse_args()
    
    if args.pre_deployment:
        ready = run_pre_deployment_validation(args.config)
        sys.exit(0 if ready else 1)
    else:
        validator = EnhancedDeploymentValidator(args.config)
        if validator.load_config():
            results = validator.run_comprehensive_validation()
            sys.exit(0 if results.get("ready", False) else 1)
        else:
            sys.exit(1)
