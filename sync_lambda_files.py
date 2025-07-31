#!/usr/bin/env python3
"""
Sync backend files to lambda_function directory for deployment.
This ensures the Lambda function has all necessary files.

NOTE: s3_vector_utils.py is intentionally excluded from sync because
the Lambda version has different optimizations than the backend version.
See docs/s3-vector-utils-versions.md for details.
"""

import os
import shutil
from pathlib import Path

def sync_files():
    """Sync files from src/backend to lambda_function directory."""
    
    # Define source and destination directories
    src_dir = Path("src/backend")
    dest_dir = Path("lambda_function")
    
    # Files to sync (only the core application files)
    # NOTE: s3_vector_utils.py is excluded - see docs/s3-vector-utils-versions.md
    files_to_sync = [
        "constants.py",
        "logging_config.py", 
        "validation.py",
        "error_handler.py",
        "aws_utils.py",
        "bedrock_utils.py",
        "cache_manager.py",
        "model_config.py",
        # "s3_vector_utils.py",  # EXCLUDED - Different versions for Lambda vs Backend
        "token_utils.py",
        "lambda_handler.py",
        "logging_utils.py",
        "__init__.py"
    ]
    
    print("🔄 Syncing backend files to lambda_function directory...")
    print("⚠️  Note: s3_vector_utils.py is excluded (different Lambda version exists)")
    
    # Create destination directory if it doesn't exist
    dest_dir.mkdir(exist_ok=True)
    
    synced_files = []
    
    for file_name in files_to_sync:
        src_file = src_dir / file_name
        dest_file = dest_dir / file_name
        
        if src_file.exists():
            shutil.copy2(src_file, dest_file)
            print(f"✅ Synced {file_name}")
            synced_files.append(file_name)
        else:
            print(f"⚠️  Warning: {file_name} not found in {src_dir}")
    
    print(f"\n📊 Synced {len(synced_files)} files:")
    for file_name in synced_files:
        print(f"   • {file_name}")
    
    print(f"\n📋 Excluded files (intentionally):")
    print(f"   • s3_vector_utils.py (Lambda version has different optimizations)")
    
    print("\n🎉 File sync completed successfully!")
    print("💡 Now run: ./deploy.sh deploy")
    print("📖 For s3_vector_utils.py details, see: docs/s3-vector-utils-versions.md")

if __name__ == "__main__":
    sync_files()
