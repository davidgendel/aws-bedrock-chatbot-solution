# Comprehensive Troubleshooting Guide

This guide provides solutions for common issues you might encounter during deployment and operation of your RAG Chatbot with the enhanced features.

## 🚨 Emergency Quick Fixes

### Deployment Failed Completely
```bash
# Try these commands in order:
./deploy.sh --recover         # Resume from last successful step
./deploy.sh rollback   # Rollback atomic deployment
./deploy.sh --clean          # Clean up and start fresh
./deploy.sh                  # Run full deployment again
```

### Chatbot Not Working on Website
1. Wait 10 minutes (AWS needs time to propagate changes)
2. Check browser console for JavaScript errors (F12 → Console tab)
3. Verify the integration code is exactly as provided
4. Clear browser cache and try again
5. Check if S3 Vectors index is properly created

### High AWS Costs
1. Check CloudWatch dashboard for unusual usage spikes
2. Verify rate limiting is enabled in API Gateway
3. Check vector index optimization status
4. Review document processing queue for stuck jobs
5. Contact AWS support if costs seem incorrect

## 📋 Pre-Deployment Issues

### AWS Account Setup Problems

**Issue**: "Cannot create AWS account"
- **Cause**: Credit card declined or verification issues
- **Solution**: 
  - Use a different credit card
  - Contact your bank to authorize AWS charges
  - Try creating account from a different browser/device

**Issue**: "AWS CLI not found"
- **Cause**: AWS CLI not installed or not in system PATH
- **Solution**:
  ```bash
  # Windows (run as administrator)
  msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi
  
  # Mac
  brew install awscli
  
  # Linux
  sudo apt install awscli  # Ubuntu/Debian
  sudo yum install awscli  # CentOS/RHEL
  ```

**Issue**: "AWS credentials not configured"
- **Cause**: AWS CLI not configured with access keys
- **Solution**:
  ```bash
  aws configure
  # Enter your Access Key ID, Secret Access Key, region, and output format
  
  # Test configuration
  aws sts get-caller-identity
  ```

### Python Environment Issues

**Issue**: "Python version too old"
- **Cause**: Python version below 3.9
- **Solution**:
  ```bash
  # Check current version
  python3 --version
  
  # Install Python 3.12+ from python.org
  # Or use pyenv for version management
  curl https://pyenv.run | bash
  pyenv install 3.12.0
  pyenv global 3.12.0
  ```

**Issue**: "pip install fails"
- **Cause**: Missing system dependencies or permissions
- **Solution**:
  ```bash
  # Update pip first
  python3 -m pip install --upgrade pip
  
  # Install with user flag if permission issues
  pip install -r requirements.txt --user
  
  # Or use virtual environment
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

## 🚀 Deployment Issues

### Atomic Deployment Problems

**Issue**: "jq not found - using standard deployment"
- **Cause**: jq not installed (needed for atomic deployment)
- **Solution**:
  ```bash
  # Install jq for better deployment experience
  sudo apt install jq      # Ubuntu/Debian
  sudo yum install jq      # CentOS/RHEL
  brew install jq          # macOS
  
  # Then retry atomic deployment
  ./deploy.sh deploy
  ```

**Issue**: "Deployment stuck in progress"
- **Cause**: CloudFormation stack in UPDATE_IN_PROGRESS state
- **Solution**:
  ```bash
  # Check stack status
  aws cloudformation describe-stacks --stack-name ChatbotRagStack
  
  # If stuck, cancel update and retry
  aws cloudformation cancel-update-stack --stack-name ChatbotRagStack
  
  # Wait for cancellation, then retry
  ./deploy.sh deploy
  ```

**Issue**: "Rollback failed"
- **Cause**: Resources in inconsistent state
- **Solution**:
  ```bash
  # Manual cleanup
  python3 scripts/cleanup_database.py --force
  
  # Delete CloudFormation stack manually
  aws cloudformation delete-stack --stack-name ChatbotRagStack
  
  # Wait for deletion, then redeploy
  ./deploy.sh deploy
  ```

### CDK Bootstrap Issues

**Issue**: "CDK bootstrap failed"
- **Cause**: Insufficient permissions or region issues
- **Solution**:
  ```bash
  # Check current region
  aws configure get region
  
  # Bootstrap specific region
  cdk bootstrap aws://ACCOUNT-ID/REGION
  
  # Or bootstrap with specific profile
  cdk bootstrap --profile your-profile
  ```

**Issue**: "CDK version mismatch"
- **Cause**: Outdated CDK version
- **Solution**:
  ```bash
  # Update CDK globally
  npm install -g aws-cdk@latest
  
  # Verify version
  cdk --version
  
  # Re-bootstrap if needed
  cdk bootstrap
  ```

## 🤖 Runtime Issues

### Vector Storage Problems

**Issue**: "S3 Vectors index not found"
- **Cause**: Vector index not created or misconfigured
- **Solution**:
  ```bash
  # Check if index exists
  python3 -c "
  from src.backend.s3_vector_utils import list_vector_indexes
  print(list_vector_indexes())
  "
  
  # Create index manually
  python3 -c "
  from src.backend.s3_vector_utils import create_vector_index
  create_vector_index('chatbot-index')
  "
  ```

**Issue**: "Vector similarity search slow"
- **Cause**: Index not optimized or too many vectors
- **Solution**:
  ```bash
  # Optimize vector index
  python3 scripts/manage_vector_indexes.py --optimize
  
  # Check optimization status
  python3 scripts/manage_vector_indexes.py --status
  
  # Clean up old vectors
  python3 scripts/cleanup_vectors.py --days 90
  ```

**Issue**: "Document processing failed"
- **Cause**: Unsupported format or processing errors
- **Solution**:
  ```bash
  # Check supported formats
  python3 -c "
  from src.backend.document_processor import handler
  result = handler({'action': 'status'}, None)
  print('Supported formats:', result['body']['supported_file_types'])
  "
  
  # Process document manually
  python3 -c "
  from src.backend.document_processor import process_document
  result = process_document('your-bucket', 'document.pdf')
  print(result)
  "
  ```

### Performance Issues

**Issue**: "Chatbot responses are slow"
- **Cause**: Cold starts, unoptimized vectors, or cache misses
- **Solution**:
  ```bash
  # Warm up Lambda functions
  curl -X POST https://your-api-endpoint/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "test", "session_id": "warmup"}'
  
  # Check cache performance
  python3 -c "
  from src.backend.cache_manager import get_cache_stats
  print(get_cache_stats())
  "
  
  # Optimize vector index
  python3 scripts/manage_vector_indexes.py --optimize
  ```

**Issue**: "High memory usage in Lambda"
- **Cause**: Large vector operations or memory leaks
- **Solution**:
  ```bash
  # Check Lambda metrics
  aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name MemoryUtilization \
    --dimensions Name=FunctionName,Value=ChatbotFunction \
    --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average,Maximum
  
  # Enable async processing to reduce memory usage
  export USE_ASYNC_PROCESSING=true
  ```

### API Gateway Issues

**Issue**: "API Gateway timeout"
- **Cause**: Lambda function taking too long
- **Solution**:
  ```bash
  # Check Lambda duration
  aws logs filter-log-events \
    --log-group-name /aws/lambda/ChatbotFunction \
    --filter-pattern "REPORT" \
    --limit 10
  
  # Enable streaming responses
  # Check widget.js for streaming configuration
  
  # Optimize document processing
  python3 scripts/manage_vector_indexes.py --optimize
  ```

**Issue**: "CORS errors in browser"
- **Cause**: CORS not properly configured
- **Solution**:
  ```bash
  # Check API Gateway CORS settings
  aws apigateway get-resource --rest-api-id YOUR_API_ID --resource-id YOUR_RESOURCE_ID
  
  # Redeploy to fix CORS
  ./deploy.sh
  ```

## 🔧 Advanced Troubleshooting

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Set debug environment variables
export DEBUG=true
export LOG_LEVEL=DEBUG

# Run with debug logging
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from src.backend.lambda_handler import handler
result = handler({'httpMethod': 'POST', 'body': '{\"message\": \"test\"}'}, None)
print(result)
"
```

### Performance Profiling

```bash
# Profile vector operations
python3 -c "
import time
from src.backend.s3_vector_utils import calculate_batch_cosine_similarity
import numpy as np

# Generate test data
query = np.random.rand(1536).tolist()
vectors = [np.random.rand(1536).tolist() for _ in range(1000)]

# Benchmark
start = time.time()
similarities = calculate_batch_cosine_similarity(query, vectors)
end = time.time()

print(f'Processed 1000 vectors in {end-start:.3f}s')
print(f'Throughput: {1000/(end-start):.0f} vectors/second')
"
```

### Memory Analysis

```bash
# Check memory usage patterns
python3 -c "
import psutil
import gc
from src.backend.s3_vector_utils import query_similar_vectors

# Monitor memory before
mem_before = psutil.Process().memory_info().rss / 1024 / 1024

# Run vector query
query_embedding = [0.1] * 1536
results = query_similar_vectors(query_embedding, limit=10)

# Monitor memory after
mem_after = psutil.Process().memory_info().rss / 1024 / 1024
print(f'Memory usage: {mem_before:.1f}MB -> {mem_after:.1f}MB')
print(f'Memory increase: {mem_after - mem_before:.1f}MB')

# Force garbage collection
gc.collect()
mem_final = psutil.Process().memory_info().rss / 1024 / 1024
print(f'After GC: {mem_final:.1f}MB')
"
```

## 📊 Monitoring and Alerts

### Set Up CloudWatch Alarms

```bash
# Create alarm for high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name "ChatbotHighErrorRate" \
  --alarm-description "High error rate in chatbot" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=ChatbotFunction \
  --evaluation-periods 2

# Create alarm for high costs
aws cloudwatch put-metric-alarm \
  --alarm-name "ChatbotHighCosts" \
  --alarm-description "High AWS costs" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD \
  --evaluation-periods 1
```

### Log Analysis

```bash
# Search for errors in logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/ChatbotFunction \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000

# Search for performance issues
aws logs filter-log-events \
  --log-group-name /aws/lambda/ChatbotFunction \
  --filter-pattern "[timestamp, requestId, level=ERROR]" \
  --start-time $(date -d '1 day ago' +%s)000
```

## 🆘 Getting Help

### Automated Error Analysis

```bash
# Run automated error analysis
python3 scripts/error_analyzer.py deployment.log

# Get recovery suggestions
python3 scripts/recovery_manager.py --analyze --suggest
```

### Manual Support

1. **Check Documentation**: [FAQ](faq.md), [User Guide](user-guide.md)
2. **Search Issues**: Look for similar problems in project issues
3. **Collect Information**:
   ```bash
   # Gather system info
   echo "System: $(uname -a)"
   echo "Python: $(python3 --version)"
   echo "AWS CLI: $(aws --version)"
   echo "CDK: $(cdk --version)"
   echo "Region: $(aws configure get region)"
   
   # Check deployment status
   ./deploy.sh status
   
   # Get recent logs
   tail -50 deployment.log
   ```

### Emergency Contacts

- **AWS Support**: If you have AWS Support plan
- **Community**: GitHub Issues for community support
- **Documentation**: Always check latest documentation

---

## 🎯 Prevention Tips

1. **Regular Updates**: Keep dependencies updated
2. **Monitoring**: Set up proper monitoring and alerts
3. **Testing**: Test deployments in staging first
4. **Backups**: Regular backups of configuration
5. **Documentation**: Keep deployment notes updated

**Remember**: Most issues can be resolved by checking logs, verifying configuration, and using the recovery tools provided.
  ```

**Issue**: "AWS credentials invalid"
- **Cause**: Incorrect Access Key or Secret Key
- **Solution**:
  1. Go to AWS Console → IAM → Users → Your User → Security Credentials
  2. Create new Access Key (deactivate old one)
  3. Run `aws configure` with new credentials
  4. Test with: `aws sts get-caller-identity`

### Python Environment Issues

**Issue**: "Python not found"
- **Cause**: Python not installed or not in system PATH
- **Solution**:
  ```bash
  # Check if Python is installed
  python3 --version
  
  # If not found, install:
  # Windows: Download from python.org
  # Mac: brew install python3
  # Linux: sudo apt install python3 python3-pip
  ```

**Issue**: "pip not found"
- **Cause**: pip not installed with Python
- **Solution**:
  ```bash
  # Install pip
  python3 -m ensurepip --upgrade
  
  # Or download get-pip.py and run:
  python3 get-pip.py
  ```

**Issue**: "Virtual environment creation failed"
- **Cause**: Insufficient permissions or disk space
- **Solution**:
  ```bash
  # Check disk space
  df -h .
  
  # Try creating venv in different location
  python3 -m venv ~/chatbot-venv
  source ~/chatbot-venv/bin/activate
  ```

## 🔧 Deployment Issues

### Permission Errors

**Issue**: "Access denied" or "Insufficient permissions"
- **Cause**: AWS user lacks required permissions
- **Solution**:
  1. In AWS Console, go to IAM → Users → Your User
  2. Click "Attach policies directly"
  3. Add "AdministratorAccess" policy (for initial deployment)
  4. After deployment, you can reduce permissions

**Issue**: "Cannot assume role"
- **Cause**: Cross-account role issues or trust policy problems
- **Solution**:
  1. Ensure you're deploying to the correct AWS account
  2. Check that your user has `sts:AssumeRole` permissions
  3. Verify the role trust policy allows your user

### Resource Limit Issues

**Issue**: "Service limit exceeded"
- **Cause**: AWS account limits reached
- **Solution**:
  1. Check AWS Service Quotas console
  2. Request limit increases for:
     - Lambda concurrent executions
     - RDS instances
     - VPC resources
  3. Consider deploying in a different region

**Issue**: "Availability Zone has no available capacity"
- **Cause**: AWS capacity issues in selected AZ
- **Solution**:
  1. Try deploying in a different region
  2. Wait and retry (capacity issues are usually temporary)
  3. Modify CDK code to use different AZ

### Network and Connectivity Issues

**Issue**: "Timeout connecting to AWS services"
- **Cause**: Network connectivity or firewall issues
- **Solution**:
  1. Check internet connection
  2. Verify corporate firewall allows AWS API calls
  3. Try using different network (mobile hotspot)
  4. Configure proxy settings if needed:
     ```bash
     export HTTP_PROXY=http://proxy.company.com:8080
     export HTTPS_PROXY=http://proxy.company.com:8080
     ```

**Issue**: "SSL certificate verification failed"
- **Cause**: Corporate firewall or proxy intercepting SSL
- **Solution**:
  ```bash
  # Temporary workaround (not recommended for production)
  export AWS_CA_BUNDLE=""
  
  # Better solution: Configure proper certificates
  export AWS_CA_BUNDLE=/path/to/corporate/ca-bundle.crt
  ```

## 🗄️ Database Issues

### Connection Problems

**Issue**: "Cannot connect to database"
- **Cause**: Security group rules or network configuration
- **Solution**:
  1. Check RDS instance status in AWS Console
  2. Verify security group allows inbound connections on port 5432
  3. For regions other than us-east-1, update security group rules:
     ```bash
     # Get your database security group ID
     aws cloudformation describe-stacks --stack-name "ChatbotRagStack" \
       --query "Stacks[0].Outputs[?OutputKey=='DatabaseSecurityGroupId'].OutputValue" \
       --output text
     
     # Add rule for your region (replace sg-xxxxxxxx and REGION)
     aws ec2 authorize-security-group-ingress \
       --group-id sg-xxxxxxxx \
       --protocol tcp \
       --port 5432 \
       --cidr "0.0.0.0/0" \
       --region REGION
     ```

**Issue**: "Database credentials not found"
- **Cause**: Secrets Manager secret not created or accessible
- **Solution**:
  1. Check Secrets Manager in AWS Console
  2. Verify Lambda has permission to access secret
  3. Manually create secret if missing:
     ```bash
     aws secretsmanager create-secret \
       --name "ChatbotRagStack-DatabaseSecret" \
       --description "Database credentials for RAG chatbot" \
       --secret-string '{"username":"postgres","password":"your-password","host":"your-host","port":5432,"dbname":"chatbot"}'
     ```

### Performance Issues

**Issue**: "Database queries are slow"
- **Cause**: Insufficient database resources or missing indexes
- **Solution**:
  1. Upgrade RDS instance type (t4g.micro → t4g.small)
  2. Check for missing indexes on vector columns
  3. Monitor database performance in CloudWatch
  4. Consider read replicas for high-traffic scenarios

**Issue**: "Database storage full"
- **Cause**: Too many documents or large document sizes
- **Solution**:
  1. Increase allocated storage in RDS
  2. Clean up old document chunks:
     ```bash
     python -m scripts.cleanup_database --older-than 30
     ```
  3. Optimize document chunking strategy

## 🤖 API and Lambda Issues

### Function Errors

**Issue**: "Lambda function timeout"
- **Cause**: Function taking too long to process
- **Solution**:
  1. Increase Lambda timeout in CDK configuration
  2. Optimize database queries
  3. Implement connection pooling
  4. Consider using provisioned concurrency

**Issue**: "Lambda out of memory"
- **Cause**: Insufficient memory allocation
- **Solution**:
  1. Increase Lambda memory in CDK configuration
  2. Optimize code to use less memory
  3. Process documents in smaller batches

**Issue**: "Cold start issues"
- **Cause**: Lambda functions not warmed up
- **Solution**:
  1. Enable provisioned concurrency in config.json:
     ```json
     "lambda": {
       "chatbot": {
         "provisionedConcurrency": {
           "enabled": true,
           "concurrentExecutions": 2
         }
       }
     }
     ```
  2. Implement Lambda warming strategies

### API Gateway Issues

**Issue**: "API Gateway 403 Forbidden"
- **Cause**: API key missing or invalid
- **Solution**:
  1. Check API key in AWS Console → API Gateway → API Keys
  2. Verify API key is included in widget configuration
  3. Ensure API key is associated with usage plan

**Issue**: "CORS errors in browser"
- **Cause**: Cross-origin requests blocked
- **Solution**:
  1. Verify CORS is enabled in API Gateway
  2. Check that your domain is allowed in CORS settings
  3. Add wildcard (*) for testing (not recommended for production)

**Issue**: "Rate limiting errors"
- **Cause**: Too many requests from single source
- **Solution**:
  1. Increase rate limits in config.json
  2. Implement client-side request queuing
  3. Use exponential backoff in widget

## 📄 Document Processing Issues

### Upload Problems

**Issue**: "Document upload fails"
- **Cause**: File format not supported or file too large
- **Solution**:
  1. Check supported formats: PDF, TXT, DOCX, MD, HTML, PNG, JPG
  2. Reduce file size (max 10MB per file)
  3. Convert to supported format
  4. Check S3 bucket permissions

**Issue**: "Text extraction fails"
- **Cause**: Corrupted file or unsupported format
- **Solution**:
  1. Try opening file in original application
  2. Re-save file in same format
  3. Convert to plain text format
  4. Check Textract service limits

### Processing Errors

**Issue**: "Chunking fails"
- **Cause**: Document structure issues or memory problems
- **Solution**:
  1. Break large documents into smaller files
  2. Remove complex formatting
  3. Check document for special characters
  4. Increase Lambda memory allocation

**Issue**: "Embedding generation fails"
- **Cause**: Bedrock service issues or quota limits
- **Solution**:
  1. Check Bedrock service status
  2. Verify model access in Bedrock console
  3. Request quota increases if needed
  4. Retry with exponential backoff

## 🌐 Widget Integration Issues

### Display Problems

**Issue**: "Widget not appearing on website"
- **Cause**: JavaScript errors or incorrect integration
- **Solution**:
  1. Check browser console for errors (F12 → Console)
  2. Verify script URL is correct and accessible
  3. Ensure container div exists: `<div id="chatbot-container"></div>`
  4. Check for conflicting CSS or JavaScript

**Issue**: "Widget appears but doesn't respond"
- **Cause**: API connectivity issues
- **Solution**:
  1. Check network tab in browser dev tools
  2. Verify API endpoint is accessible
  3. Check API key configuration
  4. Test API directly with curl:
     ```bash
     curl -X POST "https://your-api-endpoint/chat" \
       -H "Content-Type: application/json" \
       -H "x-api-key: your-api-key" \
       -d '{"message": "test"}'
     ```

### Styling Issues

**Issue**: "Widget doesn't match website design"
- **Cause**: CSS conflicts or theme configuration
- **Solution**:
  1. Customize theme in widget initialization:
     ```javascript
     SmallBizChatbot.init({
       containerId: 'chatbot-container',
       theme: {
         primaryColor: '#your-brand-color',
         fontFamily: 'Your-Font, sans-serif',
         borderRadius: '8px'
       }
     });
     ```
  2. Add custom CSS to override widget styles
  3. Use browser dev tools to inspect and modify styles

## 💰 Cost and Billing Issues

### Unexpected Charges

**Issue**: "AWS bill higher than expected"
- **Cause**: Unexpected usage or resource configuration
- **Solution**:
  1. Check AWS Cost Explorer for detailed breakdown
  2. Review CloudWatch metrics for usage spikes
  3. Verify rate limiting is working
  4. Check for runaway processes or loops
  5. Consider setting up billing alerts

**Issue**: "Free tier exceeded"
- **Cause**: Usage beyond AWS free tier limits
- **Solution**:
  1. Monitor free tier usage in AWS Console
  2. Optimize resource usage
  3. Consider pausing non-essential resources
  4. Upgrade to paid tier if needed

### Resource Optimization

**Issue**: "Want to reduce costs"
- **Solution**:
  1. Use smaller RDS instance during low-traffic periods
  2. Disable provisioned concurrency if not needed
  3. Implement more aggressive caching
  4. Clean up old logs and data regularly
  5. Use reserved instances for predictable workloads

## 🔍 Monitoring and Debugging

### Log Analysis

**Issue**: "Need to debug issues"
- **Solution**:
  1. Check CloudWatch logs:
     ```bash
     aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ChatbotRagStack"
     aws logs get-log-events --log-group-name "/aws/lambda/ChatbotRagStack-ChatbotFunction" --log-stream-name "LATEST"
     ```
  2. Enable debug logging in Lambda functions
  3. Use X-Ray tracing for performance analysis
  4. Set up CloudWatch alarms for critical metrics

### Performance Monitoring

**Issue**: "Want to monitor performance"
- **Solution**:
  1. Set up CloudWatch dashboard
  2. Monitor key metrics:
     - Lambda duration and errors
     - API Gateway latency and errors
     - Database connections and query time
     - Bedrock API calls and latency
  3. Set up alerts for threshold breaches
  4. Use AWS Personal Health Dashboard

## 🆘 Emergency Procedures

### Complete System Failure

1. **Check AWS Service Health Dashboard** for outages
2. **Review recent changes** in CloudFormation
3. **Rollback to previous version** if needed:
   ```bash
   aws cloudformation cancel-update-stack --stack-name ChatbotRagStack
   ```
4. **Contact AWS Support** if infrastructure issues persist

### Data Recovery

1. **Database issues**: Restore from automated backup
2. **Document loss**: Re-upload from local documents folder
3. **Configuration loss**: Restore from backup files in `.deployment_backup`

### Security Incidents

1. **Rotate API keys** immediately
2. **Check CloudTrail logs** for suspicious activity
3. **Update security groups** to restrict access
4. **Contact AWS Security** if breach suspected

## 📞 Getting Additional Help

### Self-Help Resources
1. **AWS Documentation**: docs.aws.amazon.com
2. **AWS Forums**: forums.aws.amazon.com
3. **Stack Overflow**: stackoverflow.com (tag: aws)
4. **GitHub Issues**: Check the project repository

### Professional Support
1. **AWS Support Plans**: Consider Business or Enterprise support
2. **AWS Professional Services**: For complex deployments
3. **Third-party consultants**: For ongoing maintenance

### Contact Information
- **Emergency**: Use AWS Support (if you have a support plan)
- **Non-urgent**: Create GitHub issue in project repository
- **Developer**: Contact the person who provided this solution

## 📝 Prevention Tips

1. **Regular backups**: Automate database and configuration backups
2. **Monitoring**: Set up comprehensive monitoring and alerting
3. **Testing**: Test changes in development environment first
4. **Documentation**: Keep deployment notes and configuration changes
5. **Updates**: Regularly update dependencies and AWS services
6. **Security**: Regularly review and update security configurations

Remember: Most issues can be resolved by following this guide systematically. When in doubt, start with the simplest solutions first!
