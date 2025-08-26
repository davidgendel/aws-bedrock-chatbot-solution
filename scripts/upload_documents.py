#!/usr/bin/env python3
"""
Document upload script that processes documents locally and uploads results to S3.
This replaces the Lambda-based document processing with local processing.
"""

import argparse
import sys
from pathlib import Path

# Import the local document processor
try:
    from process_documents_locally import LocalDocumentProcessor
except ImportError:
    from .process_documents_locally import LocalDocumentProcessor

def main():
    """Main function - wrapper around the local document processor."""
    parser = argparse.ArgumentParser(description="Upload and process documents locally")
    parser.add_argument("--file", help="Process a single file")
    parser.add_argument("--folder", help="Process all files in a folder")
    parser.add_argument("--recursive", action="store_true", help="Process folder recursively")
    parser.add_argument("--document-id", help="Document ID for single file processing")
    parser.add_argument("--batch", action="store_true", help="Enable batch processing mode")
    parser.add_argument("--config", help="Path to config file")
    
    args = parser.parse_args()
    
    if not any([args.file, args.folder]):
        parser.print_help()
        sys.exit(1)
    
    # Use the local document processor
    processor = LocalDocumentProcessor(args.config)
    
    try:
        if args.file:
            result = processor.process_file(args.file, args.document_id)
            print(f"Processing result: {result}")
        elif args.folder:
            result = processor.process_folder(args.folder, args.recursive)
            print(f"Processing summary:")
            print(f"  Total files: {result['total_files']}")
            print(f"  Processed: {result['processed']}")
            print(f"  Skipped: {result['skipped']}")
            print(f"  Errors: {result['errors']}")
            
            if result['errors'] > 0:
                print("\nErrors encountered:")
                for detail in result['details']:
                    if detail['result']['status'] == 'error':
                        print(f"  {detail['file']}: {detail['result']['error']}")
                        
    except Exception as e:
        print(f"Upload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
