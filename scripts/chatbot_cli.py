#!/usr/bin/env python3
"""Unified CLI for RAG Chatbot operations."""
import argparse
import sys
import signal
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

def timeout_handler(signum, frame):
    """Handle timeout signal."""
    print("\n❌ Operation timed out")
    sys.exit(1)

def main():
    # Set timeout for operations
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(60)  # 60 second timeout
    
    parser = argparse.ArgumentParser(description="RAG Chatbot Management CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy the chatbot')
    deploy_parser.add_argument('--region', help='AWS region')
    deploy_parser.add_argument('--rollback-on-failure', action='store_true', default=True)
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate environment')
    
    # Vector commands
    vector_parser = subparsers.add_parser('vector', help='Vector operations')
    vector_subparsers = vector_parser.add_subparsers(dest='vector_command')
    vector_subparsers.add_parser('list', help='List indexes')
    
    info_parser = vector_subparsers.add_parser('info', help='Show index information')
    info_parser.add_argument('index_name', help='Index name to show info for')
    
    optimize_parser = vector_subparsers.add_parser('optimize', help='Optimize index')
    optimize_parser.add_argument('index_name', nargs='?', help='Index name to optimize')
    
    vector_subparsers.add_parser('stats', help='Show statistics')
    vector_subparsers.add_parser('clear-cache', help='Clear caches')
    
    create_parser = vector_subparsers.add_parser('create', help='Create new index')
    create_parser.add_argument('index_name', help='Index name to create')
    create_parser.add_argument('--dimensions', type=int, default=1536, help='Vector dimensions')
    
    delete_parser = vector_subparsers.add_parser('delete', help='Delete index')
    delete_parser.add_argument('index_name', help='Index name to delete')
    delete_parser.add_argument('--force', action='store_true', help='Force deletion')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup resources')
    cleanup_parser.add_argument('--s3-only', action='store_true', help='Cleanup S3 resources only')
    
    # Cleanup-s3 alias for backward compatibility
    cleanup_s3_parser = subparsers.add_parser('cleanup-s3', help='Cleanup S3 resources only (alias)')
    
    # Status command
    subparsers.add_parser('status', help='Show deployment status')
    
    # Rollback command
    subparsers.add_parser('rollback', help='Rollback deployment')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # Import managers only when needed to avoid hanging on import
        if args.command == 'deploy':
            from deployment_manager import DeploymentManager
            return DeploymentManager().deploy(args)
        elif args.command == 'validate':
            from validation_manager import ValidationManager
            return ValidationManager().validate(args)
        elif args.command == 'vector':
            from vector_manager import VectorManager
            return VectorManager().execute(args)
        elif args.command == 'cleanup':
            from cleanup_manager import CleanupManager
            return CleanupManager().cleanup(args)
        elif args.command == 'cleanup-s3':
            from cleanup_manager import CleanupManager
            class S3OnlyArgs:
                s3_only = True
            return CleanupManager().cleanup(S3OnlyArgs())
        elif args.command == 'status':
            from deployment_manager import DeploymentManager
            return DeploymentManager().status(args)
        elif args.command == 'rollback':
            from deployment_manager import DeploymentManager
            return DeploymentManager().rollback(args)
        else:
            parser.print_help()
            return 1
            
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        signal.alarm(0)  # Cancel timeout

if __name__ == "__main__":
    sys.exit(main())
