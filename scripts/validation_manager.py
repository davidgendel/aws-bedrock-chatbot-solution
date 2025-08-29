#!/usr/bin/env python3
"""Environment validation manager."""

import sys
import subprocess
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from aws_config import get_aws_region, create_s3_client, create_s3vectors_client

class ValidationManager:
    """Environment validation with proper error handling."""
    
    def validate(self, args) -> int:
        """Validate environment setup."""
        print("🔍 Validating environment...")
        
        checks = [
            self._check_aws_credentials,
            self._check_aws_region,
            self._check_s3_access,
            self._check_s3vectors_access,
            self._check_python_version,
            self._check_required_files
        ]
        
        failed_checks = 0
        for check in checks:
            try:
                if not check():
                    failed_checks += 1
            except Exception as e:
                print(f"❌ Check failed with error: {e}")
                failed_checks += 1
        
        if failed_checks == 0:
            print("✅ All validation checks passed")
            return 0
        else:
            print(f"❌ {failed_checks} validation checks failed")
            return 1
    
    def _check_aws_credentials(self) -> bool:
        """Check AWS credentials."""
        try:
            create_s3_client()
            print("✅ AWS credentials configured")
            return True
        except RuntimeError as e:
            print(f"❌ {e}")
            return False
    
    def _check_aws_region(self) -> bool:
        """Check AWS region configuration."""
        region = get_aws_region()
        print(f"✅ AWS region: {region}")
        return True
    
    def _check_s3_access(self) -> bool:
        """Check S3 service access."""
        try:
            s3_client = create_s3_client()
            s3_client.list_buckets()
            print("✅ S3 service accessible")
            return True
        except Exception as e:
            print(f"❌ S3 service not accessible: {e}")
            return False
    
    def _check_s3vectors_access(self) -> bool:
        """Check S3 Vectors service access."""
        try:
            s3vectors_client = create_s3vectors_client()
            s3vectors_client.list_vector_buckets()
            print("✅ S3 Vectors service accessible")
            return True
        except RuntimeError as e:
            print(f"❌ {e}")
            return False
        except Exception as e:
            print(f"❌ S3 Vectors service not accessible: {e}")
            return False
    
    def _check_python_version(self) -> bool:
        """Check Python version."""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            print(f"✅ Python {version.major}.{version.minor}")
            return True
        else:
            print(f"❌ Python {version.major}.{version.minor} (requires 3.8+)")
            return False
    
    def _check_required_files(self) -> bool:
        """Check required files exist."""
        required_files = [
            'config.json',
            'src/infrastructure/cdk_stack.py'
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"❌ Missing files: {', '.join(missing_files)}")
            return False
        else:
            print("✅ Required files present")
            return True
