#!/usr/bin/env python3
"""
Interactive setup wizard for RAG Chatbot deployment.
This script provides a user-friendly interface for non-developers.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ANSI colors for better user experience
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

class SetupWizard:
    def __init__(self):
        self.config = {}
        self.config_file = "config.json"
        
    def print_header(self):
        """Print welcome header."""
        print(f"\n{Colors.BLUE}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.NC}")
        print(f"{Colors.BLUE}║{Colors.NC} {Colors.BOLD}🤖 RAG Chatbot Setup Wizard{Colors.NC}")
        print(f"{Colors.BLUE}║{Colors.NC}")
        print(f"{Colors.BLUE}║{Colors.NC} Welcome! This wizard will help you set up your AI chatbot.")
        print(f"{Colors.BLUE}║{Colors.NC} We'll ask you a few questions to customize it for your business.")
        print(f"{Colors.BLUE}║{Colors.NC}")
        print(f"{Colors.BLUE}║{Colors.NC} {Colors.CYAN}Estimated time: 5-10 minutes{Colors.NC}")
        print(f"{Colors.BLUE}║{Colors.NC} {Colors.CYAN}Monthly cost: Starting at $11.45{Colors.NC}")
        print(f"{Colors.BLUE}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.NC}")
    
    def print_section(self, title: str):
        """Print section header."""
        print(f"\n{Colors.CYAN}📋 {title}{Colors.NC}")
        print(f"{Colors.CYAN}{'─' * (len(title) + 4)}{Colors.NC}")
    
    def prompt_input(self, question: str, default: str = "", validation_func=None, help_text: str = "") -> str:
        """Prompt user for input with validation."""
        while True:
            if help_text:
                print(f"{Colors.YELLOW}💡 {help_text}{Colors.NC}")
            
            if default:
                prompt = f"{Colors.CYAN}{question} [{default}]: {Colors.NC}"
            else:
                prompt = f"{Colors.CYAN}{question}: {Colors.NC}"
            
            try:
                response = input(prompt).strip()
                
                # Use default if no response
                if not response and default:
                    response = default
                
                # Validate response
                if validation_func:
                    is_valid, error_msg = validation_func(response)
                    if not is_valid:
                        print(f"{Colors.RED}❌ {error_msg}{Colors.NC}")
                        continue
                
                return response
                
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Setup cancelled by user.{Colors.NC}")
                sys.exit(0)
    
    def prompt_choice(self, question: str, choices: List[Tuple[str, str]], default: int = 0) -> str:
        """Prompt user to choose from a list of options."""
        while True:
            print(f"\n{Colors.CYAN}{question}{Colors.NC}")
            
            for i, (value, description) in enumerate(choices, 1):
                marker = "→" if i == default + 1 else " "
                print(f"{Colors.CYAN}{marker} {i}. {description}{Colors.NC}")
            
            try:
                choice = input(f"\n{Colors.CYAN}Enter choice [1-{len(choices)}] or press Enter for default: {Colors.NC}").strip()
                
                if not choice:
                    return choices[default][0]
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(choices):
                    return choices[choice_num - 1][0]
                else:
                    print(f"{Colors.RED}❌ Please enter a number between 1 and {len(choices)}{Colors.NC}")
                    
            except ValueError:
                print(f"{Colors.RED}❌ Please enter a valid number{Colors.NC}")
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Setup cancelled by user.{Colors.NC}")
                sys.exit(0)
    
    def validate_region(self, region: str) -> Tuple[bool, str]:
        """Validate AWS region format."""
        if re.match(r'^[a-z]{2}-[a-z]+-[0-9]+$', region):
            return True, ""
        return False, "Invalid region format. Expected format: us-east-1, eu-west-1, etc."
    
    def validate_color(self, color: str) -> Tuple[bool, str]:
        """Validate hex color format."""
        if re.match(r'^#[0-9A-Fa-f]{6}$', color):
            return True, ""
        return False, "Invalid color format. Use hex format like #4287f5"
    
    def get_aws_regions(self) -> List[Tuple[str, str]]:
        """Get list of common AWS regions."""
        return [
            ("us-east-1", "US East (N. Virginia) - Recommended for US customers"),
            ("us-west-2", "US West (Oregon) - Good for US West Coast"),
            ("eu-west-1", "Europe (Ireland) - Recommended for European customers"),
            ("eu-central-1", "Europe (Frankfurt) - Good for Central Europe"),
            ("ap-southeast-1", "Asia Pacific (Singapore) - Good for Southeast Asia"),
            ("ap-northeast-1", "Asia Pacific (Tokyo) - Good for Japan/Korea"),
            ("ap-south-1", "Asia Pacific (Mumbai) - Good for India"),
            ("ca-central-1", "Canada (Central) - Good for Canadian customers"),
            ("sa-east-1", "South America (São Paulo) - Good for South America"),
        ]
    
    def collect_basic_info(self):
        """Collect basic information."""
        self.print_section("Basic Configuration")
        
        print(f"{Colors.CYAN}Setting up your RAG chatbot with optimal defaults...{Colors.NC}")
        print(f"{Colors.YELLOW}💡 This configuration is optimized for cost-effectiveness and performance.{Colors.NC}")
    
    def collect_technical_settings(self):
        """Collect technical settings."""
        self.print_section("Technical Settings")
        
        # AWS Region
        region = self.prompt_choice(
            "Which AWS region would you like to deploy to?",
            self.get_aws_regions()
        )
        self.config["region"] = region
        
        # Set optimal defaults for small business use
        self.config["lambda"] = {
            "chatbot": {
                "provisionedConcurrency": {
                    "enabled": True,
                    "concurrentExecutions": 1
                }
            }
        }
        
        # Set conservative rate limiting for cost control
        self.config["api"] = {
            "throttling": {
                "ratePerMinute": 10,
                "ratePerHour": 100
            }
        }
        
        # Configure S3 Vectors for document embeddings
        self.config["s3Vectors"] = {
            "indexName": "chatbot-document-vectors",
            "dimensions": 1536,  # Amazon Titan embeddings dimension
            "similarityMetric": "COSINE"
        }
    
    def collect_customization(self):
        """Collect customization preferences."""
        self.print_section("Customization")
        
        # Primary color
        primary_color = self.prompt_input(
            "What's your brand's primary color? (hex format)",
            "#4287f5",
            self.validate_color,
            "Use a hex color code like #4287f5 (blue) or #28a745 (green)"
        )
        
        # Font family
        font_families = [
            ("Arial, sans-serif", "Arial - Clean and professional"),
            ("Georgia, serif", "Georgia - Traditional and readable"),
            ("'Helvetica Neue', sans-serif", "Helvetica - Modern and sleek"),
            ("'Times New Roman', serif", "Times New Roman - Classic and formal"),
            ("Verdana, sans-serif", "Verdana - Clear and web-friendly")
        ]
        
        font_family = self.prompt_choice(
            "Which font would you like for your chatbot?",
            font_families
        )
        
        self.config["widget"] = {
            "defaultTheme": {
                "primaryColor": primary_color,
                "secondaryColor": "#f5f5f5",
                "fontFamily": font_family,
                "fontSize": "16px",
                "borderRadius": "8px"
            }
        }
    
    def collect_content_settings(self):
        """Collect content moderation settings."""
        self.print_section("Content & Safety Settings")
        
        print(f"{Colors.CYAN}Setting up content filtering for safe and professional interactions.{Colors.NC}")
        
        # Content filtering strength
        filter_strengths = [
            ("LOW", "Low - Minimal filtering, more permissive"),
            ("MEDIUM", "Medium - Balanced filtering (Recommended)"),
            ("HIGH", "High - Strict filtering, very conservative")
        ]
        
        filter_strength = self.prompt_choice(
            "How strict should content filtering be?",
            filter_strengths,
            default=1  # Medium is default
        )
        
        # Build guardrails config with recommended settings (cost-optimized)
        self.config["bedrock"] = {
            "modelId": "amazon.nova-lite-v1",
            "guardrails": {
                "createDefault": True,
                "defaultGuardrailConfig": {
                    "name": "ChatbotGuardrail",
                    "description": "Content guardrail for RAG chatbot",
                    "contentPolicyConfig": {
                        "filters": [
                            {"type": "SEXUAL", "strength": filter_strength},
                            {"type": "VIOLENCE", "strength": filter_strength},
                            {"type": "HATE", "strength": filter_strength},
                            {"type": "INSULTS", "strength": filter_strength}
                        ]
                    },
                    "wordPolicyConfig": {
                        "managedWordLists": [{"type": "PROFANITY"}],
                        "customWordLists": []
                    }
                }
            }
        }
    
    def show_cost_estimate(self):
        """Show cost estimate based on configuration."""
        self.print_section("Cost Estimate")
        
        print(f"{Colors.GREEN}💰 Estimated Monthly Cost: $11.45{Colors.NC}")
        print(f"{Colors.CYAN}   Annual Cost: $137.40{Colors.NC}")
        
        print(f"\n{Colors.YELLOW}💡 Cost includes:{Colors.NC}")
        print(f"{Colors.YELLOW}   • AI processing (Amazon Nova Lite + Titan Embeddings){Colors.NC}")
        print(f"{Colors.YELLOW}   • Vector storage (Amazon S3 Vectors){Colors.NC}")
        print(f"{Colors.YELLOW}   • API hosting (Lambda + API Gateway){Colors.NC}")
        print(f"{Colors.YELLOW}   • Security features (WAF + Guardrails){Colors.NC}")
        print(f"{Colors.YELLOW}   • Content delivery (CloudFront){Colors.NC}")
        
        print(f"\n{Colors.CYAN}Costs may vary based on actual usage. See docs/pricing.md for details.{Colors.NC}")
    
    def show_configuration_summary(self):
        """Show configuration summary."""
        self.print_section("Configuration Summary")
        
        print(f"{Colors.CYAN}AWS Region:{Colors.NC} {self.config['region']}")
        print(f"{Colors.CYAN}AI Model:{Colors.NC} Amazon Nova Lite (cost-optimized)")
        print(f"{Colors.CYAN}Primary Color:{Colors.NC} {self.config['widget']['defaultTheme']['primaryColor']}")
        print(f"{Colors.CYAN}Lambda Concurrency:{Colors.NC} {self.config['lambda']['chatbot']['provisionedConcurrency']['concurrentExecutions']}")
        print(f"{Colors.CYAN}Rate Limiting:{Colors.NC} {self.config['api']['throttling']['ratePerMinute']}/min, {self.config['api']['throttling']['ratePerHour']}/hour")
    
    def save_configuration(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"{Colors.GREEN}✅ Configuration saved to {self.config_file}{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to save configuration: {e}{Colors.NC}")
            return False
    
    def check_prerequisites(self):
        """Check if prerequisites are met."""
        self.print_section("Prerequisites Check")
        
        # Check AWS CLI
        try:
            result = subprocess.run(['aws', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ AWS CLI found{Colors.NC}")
            else:
                print(f"{Colors.RED}❌ AWS CLI not found{Colors.NC}")
                return False
        except FileNotFoundError:
            print(f"{Colors.RED}❌ AWS CLI not installed{Colors.NC}")
            print(f"{Colors.YELLOW}Please install AWS CLI: https://aws.amazon.com/cli/{Colors.NC}")
            return False
        
        # Check AWS credentials
        try:
            result = subprocess.run(['aws', 'sts', 'get-caller-identity'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ AWS credentials configured{Colors.NC}")
            else:
                print(f"{Colors.RED}❌ AWS credentials not configured{Colors.NC}")
                print(f"{Colors.YELLOW}Please run: aws configure{Colors.NC}")
                return False
        except Exception:
            print(f"{Colors.RED}❌ Error checking AWS credentials{Colors.NC}")
            return False
        
        # Check Python
        try:
            result = subprocess.run(['python3', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ Python 3 found{Colors.NC}")
            else:
                print(f"{Colors.RED}❌ Python 3 not found{Colors.NC}")
                return False
        except FileNotFoundError:
            print(f"{Colors.RED}❌ Python 3 not installed{Colors.NC}")
            print(f"{Colors.YELLOW}Please install Python 3: https://python.org{Colors.NC}")
            return False
        
        return True
    
    def run(self):
        """Run the setup wizard."""
        self.print_header()
        
        # Check prerequisites first
        if not self.check_prerequisites():
            print(f"\n{Colors.RED}❌ Prerequisites not met. Please install required software first.{Colors.NC}")
            print(f"{Colors.CYAN}See docs/deployment-guide.md for detailed instructions.{Colors.NC}")
            return False
        
        try:
            # Collect information
            self.collect_basic_info()
            self.collect_technical_settings()
            self.collect_customization()
            self.collect_content_settings()
            
            # Show summary
            self.show_configuration_summary()
            self.show_cost_estimate()
            
            # Confirm and save
            print(f"\n{Colors.CYAN}Ready to save configuration and start deployment?{Colors.NC}")
            confirm = self.prompt_choice(
                "Proceed with deployment?",
                [("yes", "Yes - Save config and deploy"), ("no", "No - Save config only"), ("cancel", "Cancel setup")],
                default=0
            )
            
            if confirm == "cancel":
                print(f"{Colors.YELLOW}Setup cancelled.{Colors.NC}")
                return False
            
            # Save configuration
            if not self.save_configuration():
                return False
            
            if confirm == "yes":
                print(f"\n{Colors.GREEN}🚀 Starting deployment...{Colors.NC}")
                print(f"{Colors.CYAN}This will take approximately 15-20 minutes.{Colors.NC}")
                print(f"{Colors.CYAN}You can monitor progress in the terminal.{Colors.NC}")
                
                # Run deployment using the consolidated script
                try:
                    deploy_script = "./deploy.sh"
                    if os.path.exists(deploy_script):
                        subprocess.run([deploy_script, "deploy"], check=True)
                        return True
                    else:
                        print(f"{Colors.RED}❌ Deployment script not found. Please ensure deploy.sh exists.{Colors.NC}")
                        return False
                except subprocess.CalledProcessError:
                    print(f"{Colors.RED}❌ Deployment failed. Check the logs for details.{Colors.NC}")
                    return False
                except FileNotFoundError:
                    print(f"{Colors.RED}❌ Deployment script not found. Please ensure deploy.sh exists.{Colors.NC}")
                    return False
            else:
                print(f"\n{Colors.GREEN}✅ Configuration saved!{Colors.NC}")
                print(f"{Colors.CYAN}Run './deploy.sh deploy' when you're ready to deploy.{Colors.NC}")
                return True
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Setup cancelled by user.{Colors.NC}")
            return False
        except Exception as e:
            print(f"\n{Colors.RED}❌ Unexpected error: {e}{Colors.NC}")
            return False

def main():
    """Main entry point."""
    wizard = SetupWizard()
    success = wizard.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
