#!/usr/bin/env python3
"""
AWS Request Signing Validation Script

This script validates the request signing implementation and provides
performance benchmarking and security verification.
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import statistics

# Add lambda_function to path for imports
sys.path.append(str(Path(__file__).parent.parent / "lambda_function"))

try:
    from aws_client_factory import AWSClientFactory
    from request_signer import RequestSigner, SigningConfig, create_signed_request
    from aws_utils import get_aws_region, configure_request_signing
except ImportError as e:
    print(f"Error importing signing modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SigningValidator:
    """Validates AWS request signing implementation."""
    
    def __init__(self):
        """Initialize the validator."""
        self.region = get_aws_region()
        self.results = {
            'configuration': {},
            'client_creation': {},
            'signing_functionality': {},
            'performance': {},
            'security': {}
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate signing configuration."""
        logger.info("🔧 Validating signing configuration...")
        
        try:
            # Load configuration
            config_path = Path(__file__).parent.parent / "config.json"
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            aws_config = config.get('aws', {})
            signing_config = aws_config.get('requestSigning', {})
            
            # Validate required fields
            required_fields = ['enabled', 'signatureVersion']
            missing_fields = [field for field in required_fields if field not in signing_config]
            
            result = {
                'config_found': True,
                'signing_config_present': bool(signing_config),
                'enabled': signing_config.get('enabled', False),
                'signature_version': signing_config.get('signatureVersion', 'unknown'),
                'missing_fields': missing_fields,
                'valid': len(missing_fields) == 0
            }
            
            if result['valid']:
                logger.info("✅ Configuration validation passed")
            else:
                logger.error(f"❌ Configuration validation failed: missing {missing_fields}")
            
            self.results['configuration'] = result
            return result
            
        except Exception as e:
            logger.error(f"❌ Configuration validation error: {e}")
            result = {'config_found': False, 'error': str(e), 'valid': False}
            self.results['configuration'] = result
            return result
    
    def validate_client_creation(self) -> Dict[str, Any]:
        """Validate signed client creation."""
        logger.info("🏭 Validating client creation...")
        
        services_to_test = ['s3', 'bedrock-runtime', 'lambda', 'cloudformation']
        results = {}
        
        for service in services_to_test:
            try:
                # Test signed client creation
                start_time = time.time()
                signed_client = AWSClientFactory.create_client(
                    service, 
                    enable_signing=True,
                    use_cache=False
                )
                signed_time = time.time() - start_time
                
                # Test unsigned client creation
                start_time = time.time()
                unsigned_client = AWSClientFactory.create_client(
                    service, 
                    enable_signing=False,
                    use_cache=False
                )
                unsigned_time = time.time() - start_time
                
                results[service] = {
                    'signed_client_created': signed_client is not None,
                    'unsigned_client_created': unsigned_client is not None,
                    'signed_creation_time': signed_time,
                    'unsigned_creation_time': unsigned_time,
                    'overhead_ms': (signed_time - unsigned_time) * 1000,
                    'valid': True
                }
                
                logger.info(f"✅ {service} client creation: {results[service]['overhead_ms']:.2f}ms overhead")
                
            except Exception as e:
                logger.error(f"❌ {service} client creation failed: {e}")
                results[service] = {
                    'error': str(e),
                    'valid': False
                }
        
        overall_valid = all(result.get('valid', False) for result in results.values())
        results['overall_valid'] = overall_valid
        
        if overall_valid:
            logger.info("✅ Client creation validation passed")
        else:
            logger.error("❌ Client creation validation failed")
        
        self.results['client_creation'] = results
        return results
    
    def validate_signing_functionality(self) -> Dict[str, Any]:
        """Validate request signing functionality."""
        logger.info("🔐 Validating signing functionality...")
        
        try:
            # Test signing configuration
            config = SigningConfig({
                'enabled': True,
                'signatureVersion': 'v4',
                'includeHeaders': ['host', 'x-amz-date', 'authorization']
            })
            
            signer = RequestSigner(config)
            
            # Test request signing
            test_headers = {
                'Host': 's3.amazonaws.com',
                'Content-Type': 'application/json'
            }
            
            signed_headers = signer.sign_request(
                method='GET',
                url='https://s3.amazonaws.com/test-bucket/test-key',
                headers=test_headers,
                payload=''
            )
            
            # Validate signature components
            has_auth_header = 'Authorization' in signed_headers
            has_date_header = 'X-Amz-Date' in signed_headers
            auth_header_valid = False
            
            if has_auth_header:
                auth_header = signed_headers['Authorization']
                auth_header_valid = (
                    'AWS4-HMAC-SHA256' in auth_header and
                    'Credential=' in auth_header and
                    'SignedHeaders=' in auth_header and
                    'Signature=' in auth_header
                )
            
            result = {
                'signer_created': True,
                'request_signed': len(signed_headers) > len(test_headers),
                'has_authorization_header': has_auth_header,
                'has_date_header': has_date_header,
                'authorization_header_valid': auth_header_valid,
                'signed_headers_count': len(signed_headers),
                'valid': has_auth_header and has_date_header and auth_header_valid
            }
            
            if result['valid']:
                logger.info("✅ Signing functionality validation passed")
            else:
                logger.error("❌ Signing functionality validation failed")
            
            self.results['signing_functionality'] = result
            return result
            
        except Exception as e:
            logger.error(f"❌ Signing functionality validation error: {e}")
            result = {'error': str(e), 'valid': False}
            self.results['signing_functionality'] = result
            return result
    
    def benchmark_performance(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmark signing performance."""
        logger.info(f"⚡ Benchmarking performance ({iterations} iterations)...")
        
        try:
            # Benchmark client creation
            signed_times = []
            unsigned_times = []
            
            for _ in range(iterations):
                # Signed client creation
                start_time = time.time()
                AWSClientFactory.create_client('s3', enable_signing=True, use_cache=False)
                signed_times.append(time.time() - start_time)
                
                # Unsigned client creation
                start_time = time.time()
                AWSClientFactory.create_client('s3', enable_signing=False, use_cache=False)
                unsigned_times.append(time.time() - start_time)
            
            # Calculate statistics
            signed_avg = statistics.mean(signed_times) * 1000
            unsigned_avg = statistics.mean(unsigned_times) * 1000
            overhead_avg = signed_avg - unsigned_avg
            
            signed_p95 = statistics.quantiles(signed_times, n=20)[18] * 1000
            unsigned_p95 = statistics.quantiles(unsigned_times, n=20)[18] * 1000
            overhead_p95 = signed_p95 - unsigned_p95
            
            result = {
                'iterations': iterations,
                'signed_avg_ms': signed_avg,
                'unsigned_avg_ms': unsigned_avg,
                'overhead_avg_ms': overhead_avg,
                'signed_p95_ms': signed_p95,
                'unsigned_p95_ms': unsigned_p95,
                'overhead_p95_ms': overhead_p95,
                'overhead_percentage': (overhead_avg / unsigned_avg) * 100,
                'acceptable_overhead': overhead_avg < 10.0  # Less than 10ms overhead
            }
            
            logger.info(f"✅ Performance benchmark completed:")
            logger.info(f"   Average overhead: {overhead_avg:.2f}ms ({result['overhead_percentage']:.1f}%)")
            logger.info(f"   P95 overhead: {overhead_p95:.2f}ms")
            
            self.results['performance'] = result
            return result
            
        except Exception as e:
            logger.error(f"❌ Performance benchmark error: {e}")
            result = {'error': str(e), 'valid': False}
            self.results['performance'] = result
            return result
    
    def validate_security(self) -> Dict[str, Any]:
        """Validate security aspects of signing."""
        logger.info("🛡️ Validating security aspects...")
        
        try:
            # Test signature generation and validation
            config = SigningConfig({'enabled': True})
            signer = RequestSigner(config)
            
            test_request = {
                'method': 'GET',
                'url': 'https://s3.amazonaws.com/test-bucket/test-key',
                'headers': {'Host': 's3.amazonaws.com'},
                'payload': ''
            }
            
            # Generate a signature
            signed_headers = signer.sign_request(**test_request)
            auth_header = signed_headers.get('Authorization', '')
            
            # Validate signature components
            has_auth_header = 'Authorization' in signed_headers
            has_date_header = 'X-Amz-Date' in signed_headers
            
            # Check authorization header format
            auth_components_valid = False
            if has_auth_header:
                auth_components_valid = all(component in auth_header for component in [
                    'AWS4-HMAC-SHA256',
                    'Credential=',
                    'SignedHeaders=',
                    'Signature='
                ])
            
            # Test different requests produce different signatures
            test_request2 = {
                'method': 'POST',
                'url': 'https://s3.amazonaws.com/test-bucket/test-key2',
                'headers': {'Host': 's3.amazonaws.com'},
                'payload': 'test-payload'
            }
            
            signed_headers2 = signer.sign_request(**test_request2)
            auth_header2 = signed_headers2.get('Authorization', '')
            
            different_requests_different_sigs = auth_header != auth_header2
            
            # Extract signature from auth header
            signature1 = auth_header.split('Signature=')[1] if 'Signature=' in auth_header else ''
            signature2 = auth_header2.split('Signature=')[1] if 'Signature=' in auth_header2 else ''
            
            signature_length_valid = len(signature1) == 64  # SHA256 hex = 64 chars
            
            result = {
                'has_authorization_header': has_auth_header,
                'has_date_header': has_date_header,
                'auth_components_valid': auth_components_valid,
                'different_requests_different_sigs': different_requests_different_sigs,
                'signature_length_valid': signature_length_valid,
                'signature_length': len(signature1),
                'valid': (has_auth_header and has_date_header and 
                         auth_components_valid and different_requests_different_sigs and 
                         signature_length_valid)
            }
            
            if result['valid']:
                logger.info("✅ Security validation passed")
            else:
                logger.error("❌ Security validation failed")
                logger.debug(f"Security validation details: {result}")
            
            self.results['security'] = result
            return result
            
        except Exception as e:
            logger.error(f"❌ Security validation error: {e}")
            result = {'error': str(e), 'valid': False}
            self.results['security'] = result
            return result
    
    def run_all_validations(self, benchmark_iterations: int = 100) -> Dict[str, Any]:
        """Run all validation tests."""
        logger.info("🚀 Starting comprehensive signing validation...")
        
        # Run all validations
        self.validate_configuration()
        self.validate_client_creation()
        self.validate_signing_functionality()
        self.benchmark_performance(benchmark_iterations)
        self.validate_security()
        
        # Calculate overall result
        validations = [
            self.results['configuration'].get('valid', False),
            self.results['client_creation'].get('overall_valid', False),
            self.results['signing_functionality'].get('valid', False),
            self.results['security'].get('valid', False)
        ]
        
        overall_valid = all(validations)
        passed_count = sum(validations)
        total_count = len(validations)
        
        self.results['summary'] = {
            'overall_valid': overall_valid,
            'passed_validations': passed_count,
            'total_validations': total_count,
            'success_rate': (passed_count / total_count) * 100
        }
        
        if overall_valid:
            logger.info("🎉 All validations passed! Request signing is working correctly.")
        else:
            logger.error(f"❌ {total_count - passed_count} validation(s) failed.")
        
        return self.results
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "="*60)
        print("🔐 AWS REQUEST SIGNING VALIDATION SUMMARY")
        print("="*60)
        
        summary = self.results.get('summary', {})
        
        print(f"Overall Status: {'✅ PASS' if summary.get('overall_valid') else '❌ FAIL'}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
        print(f"Validations: {summary.get('passed_validations', 0)}/{summary.get('total_validations', 0)}")
        
        print("\nDetailed Results:")
        print("-" * 40)
        
        # Configuration
        config_result = self.results.get('configuration', {})
        status = "✅" if config_result.get('valid') else "❌"
        print(f"{status} Configuration: {'PASS' if config_result.get('valid') else 'FAIL'}")
        
        # Client Creation
        client_result = self.results.get('client_creation', {})
        status = "✅" if client_result.get('overall_valid') else "❌"
        print(f"{status} Client Creation: {'PASS' if client_result.get('overall_valid') else 'FAIL'}")
        
        # Signing Functionality
        signing_result = self.results.get('signing_functionality', {})
        status = "✅" if signing_result.get('valid') else "❌"
        print(f"{status} Signing Functionality: {'PASS' if signing_result.get('valid') else 'FAIL'}")
        
        # Performance
        perf_result = self.results.get('performance', {})
        if 'overhead_avg_ms' in perf_result:
            overhead = perf_result['overhead_avg_ms']
            status = "✅" if perf_result.get('acceptable_overhead') else "⚠️"
            print(f"{status} Performance: {overhead:.2f}ms avg overhead")
        
        # Security
        security_result = self.results.get('security', {})
        status = "✅" if security_result.get('valid') else "❌"
        print(f"{status} Security: {'PASS' if security_result.get('valid') else 'FAIL'}")
        
        print("\n" + "="*60)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Validate AWS request signing implementation")
    parser.add_argument(
        '--benchmark-iterations',
        type=int,
        default=50,
        help='Number of iterations for performance benchmark'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for detailed results (JSON format)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run validation
    validator = SigningValidator()
    results = validator.run_all_validations(args.benchmark_iterations)
    
    # Print summary
    validator.print_summary()
    
    # Save detailed results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {args.output}")
    
    # Exit with appropriate code
    overall_valid = results.get('summary', {}).get('overall_valid', False)
    sys.exit(0 if overall_valid else 1)


if __name__ == "__main__":
    main()
