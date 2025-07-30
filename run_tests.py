#!/usr/bin/env python3
"""
Test runner script for the chatbot RAG solution.
"""
import os
import sys
import subprocess
from pathlib import Path


def run_tests(test_type="all", verbose=False, coverage=True):
    """
    Run tests with specified options.
    
    Args:
        test_type: Type of tests to run ("unit", "integration", "all")
        verbose: Enable verbose output
        coverage: Enable coverage reporting
    """
    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test type filter
    if test_type == "unit":
        cmd.extend(["-m", "unit"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type != "all":
        print(f"Unknown test type: {test_type}")
        sys.exit(1)
    
    # Add verbosity
    if verbose:
        cmd.append("-v")
    
    # Add coverage
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov"
        ])
    
    # Add test directory
    cmd.append("tests/")
    
    print(f"Running command: {' '.join(cmd)}")
    
    # Run tests
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return 1
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run tests for chatbot RAG solution")
    parser.add_argument(
        "--type", 
        choices=["unit", "integration", "all"], 
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Disable coverage reporting"
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install test dependencies first"
    )
    
    args = parser.parse_args()
    
    # Install dependencies if requested
    if args.install_deps:
        print("Installing test dependencies...")
        subprocess.run([
            "pip", "install", "-r", "requirements-dev.txt"
        ], check=True)
    
    # Run tests
    exit_code = run_tests(
        test_type=args.type,
        verbose=args.verbose,
        coverage=not args.no_coverage
    )
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
        if not args.no_coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n❌ Some tests failed!")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
