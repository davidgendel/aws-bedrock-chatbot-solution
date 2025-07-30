# Pricing Information

## Monthly Cost Estimates

| Business Size | Daily Users | Monthly Cost | Cost per User |
|---------------|-------------|--------------|---------------|
| **Small** | 50 | **$21.89** | $0.44 |
| **Medium** | 250 | **$59.64** | $0.24 |
| **Growing** | 500 | **$115.01** | $0.23 |

*Pricing based on 15 interactions per user per day with 400 tokens per interaction. Calculations use latest AWS pricing as of January 2025.*

## What's Included

Your monthly cost includes everything needed to run a production chatbot:

- ✅ **AI Processing** - Amazon Nova Lite model inference
- ✅ **Document Understanding** - Amazon Titan embeddings for RAG
- ✅ **Content Safety** - Bedrock Guardrails for content filtering
- ✅ **Serverless Hosting** - AWS Lambda with provisioned concurrency
- ✅ **Vector Storage** - Amazon S3 Vectors for native vector operations
- ✅ **Real-time Chat** - API Gateway REST and WebSocket APIs
- ✅ **Security** - AWS WAF with DDoS protection and rate limiting
- ✅ **Global CDN** - CloudFront for fast content delivery
- ✅ **Monitoring** - CloudWatch logs, metrics, and dashboards
- ✅ **Document Processing** - Amazon Textract for PDFs and images

## Cost Breakdown by Service

### Small Organization - 50 Users ($21.89/month)
- **Amazon Bedrock**: $2.42 (11%)
- **AWS Lambda**: $3.99 (18%)
- **Amazon S3 Vectors**: $6.68 (31%)
- **API Gateway**: $0.10 (0.5%)
- **CloudWatch**: $1.50 (7%)
- **AWS WAF**: $1.00 (5%)
- **Other Services**: $6.20 (28%)

### Medium Organization - 250 Users ($59.64/month)
- **Amazon Bedrock**: $12.09 (20%)
- **AWS Lambda**: $5.16 (9%)
- **Amazon S3 Vectors**: $10.88 (18%)
- **API Gateway**: $0.50 (1%)
- **CloudWatch**: $2.83 (5%)
- **AWS WAF**: $1.00 (2%)
- **Other Services**: $27.18 (45%)

### Growing Organization - 500 Users ($115.01/month)
- **Amazon Bedrock**: $24.19 (21%)
- **AWS Lambda**: $13.33 (12%)
- **Amazon S3 Vectors**: $16.75 (15%)
- **API Gateway**: $1.02 (1%)
- **CloudWatch**: $5.24 (5%)
- **AWS WAF**: $1.00 (1%)
- **Other Services**: $53.48 (45%)

## AWS Service Details

### Amazon Bedrock
- **Nova Lite Model**: $0.00006 per 1K input tokens, $0.00024 per 1K output tokens
- **Titan Embeddings v2**: $0.0001 per 1K tokens
- **Guardrails**: $0.75 per 1K units (with smart filtering to reduce costs)

### AWS Lambda (ARM64/Graviton3)
- **Provisioned Concurrency**: $0.0000097222 per GB-second
- **Requests**: $0.20 per 1M requests
- **Compute**: $0.0000133334 per GB-second
- **Memory**: 512MB for chat function, 1024MB for document processing

### Amazon S3 Vectors
- **Vector Storage**: $0.10 per GB per month
- **Vector Operations**: $0.50 per 1K vector operations (queries, inserts, updates)
- **Index Management**: $5.00 per index per month
- **Data Transfer**: Standard S3 data transfer rates apply

### Amazon S3 (Standard Storage)
- **Storage**: $0.023 per GB per month
- **GET Requests**: $0.0004 per 1K requests
- **PUT Requests**: $0.005 per 1K requests
- **Data Transfer Out**: $0.09 per GB (first 10TB)

### API Gateway
- **REST API**: $3.50 per million requests
- **WebSocket API**: $1.00 per million messages + $0.25 per million connection minutes
- **Data Transfer**: $0.09 per GB

### AWS WAF
- **Web ACL**: $1.00 per month base cost
- **Rule Evaluations**: $0.60 per million requests
- **Managed Rule Groups**: $1.00 per month per rule group

### CloudFront
- **Data Transfer**: $0.085 per GB (first 10TB)
- **HTTPS Requests**: $0.0075 per 10K requests
- **Origin Requests**: $0.0075 per 10K requests

### CloudWatch
- **Log Ingestion**: $0.50 per GB
- **Log Storage**: $0.03 per GB per month
- **Custom Metrics**: $0.30 per metric per month
- **Dashboard**: $3.00 per dashboard per month
- **Alarms**: $0.10 per alarm per month

### Amazon Textract
- **Document Processing**: $1.50 per 1K pages processed
- **Table/Form Extraction**: $15.00 per 1K pages processed

## Detailed Cost Calculations

### Calculation Methodology

**Usage Assumptions:**
- 15 interactions per user per day
- 400 tokens per interaction (200 input + 200 output)
- 30 days per month
- Document processing: 100 pages per month (one-time setup)
- Vector storage: 10GB of embeddings
- Cache hit rate: 40% (reduces repeated processing)

### Small Organization (50 users/day)
**Monthly Usage:**
- 22,500 interactions
- 9,000,000 tokens (4.5M input + 4.5M output)
- 13,500 vector queries (after 40% cache hit rate)

**Service Costs:**
- **Amazon Bedrock**: $2.42
- **AWS Lambda**: $3.99
- **Amazon S3 Vectors**: $6.68
- **API Gateway**: $0.10
- **CloudWatch**: $1.50
- **AWS WAF**: $1.00
- **Other Services**: $6.20

**Total: $21.89**

### Medium Organization (250 users/day)
**Monthly Usage:**
- 112,500 interactions
- 45,000,000 tokens (22.5M input + 22.5M output)
- 67,500 vector queries (after 40% cache hit rate)

**Service Costs:**
- **Amazon Bedrock**: $12.09
- **AWS Lambda**: $5.16
- **Amazon S3 Vectors**: $10.88
- **API Gateway**: $0.50
- **CloudWatch**: $2.83
- **AWS WAF**: $1.00
- **Other Services**: $27.18

**Total: $59.64**

### Growing Organization (500 users/day)
**Monthly Usage:**
- 225,000 interactions
- 90,000,000 tokens (45M input + 45M output)
- 135,000 vector queries (after 40% cache hit rate)

**Service Costs:**
- **Amazon Bedrock**: $24.19
- **AWS Lambda**: $13.33
- **Amazon S3 Vectors**: $16.75
- **API Gateway**: $1.02
- **CloudWatch**: $5.24
- **AWS WAF**: $1.00
- **Other Services**: $53.48

**Total: $115.01**

## Cost Efficiency Features


The solution includes several built-in features that keep costs low:

### Smart Guardrail Filtering
- Skips processing for short queries (< 18 characters)
- Skips processing for document-specific questions
- Reduces unnecessary guardrail API calls by ~55%

### Intelligent Caching
- 4-hour TTL cache for guardrail results
- Prevents reprocessing of identical content
- ~40% reduction in repeated processing

### Client-Side Pre-filtering
- Blocks obvious spam and inappropriate content before server processing
- Immediate user feedback for policy violations
- Reduces server-side processing costs

### Focused Content Filtering
- Essential content filters: HATE, VIOLENCE, SEXUAL
- High-strength filtering for efficiency
- Profanity filtering through managed word lists

### Serverless Architecture
- Pay only for actual usage
- Automatic scaling based on demand
- No infrastructure management overhead

## Regional Pricing

Pricing shown is for **US East (N. Virginia)** region. Costs may vary slightly in other AWS regions:

- **US West (Oregon)**: Similar pricing
- **Europe (Ireland)**: ~5-10% higher
- **Asia Pacific (Tokyo)**: ~10-15% higher

## Billing and Payment

- **Billing Cycle**: Monthly, based on actual AWS usage
- **Payment Method**: Through your AWS account
- **Cost Monitoring**: Built-in CloudWatch dashboards track spending
- **Alerts**: Set up billing alerts to monitor costs

## Cost Optimization Tips

### For Small Organizations
- Consider disabling provisioned concurrency initially if traffic is very low
- Use shorter log retention periods (3 days instead of 1 week)
- Monitor usage patterns for the first month

### For Medium Organizations
- Current configuration is optimal for consistent performance
- Consider implementing response caching for frequently asked questions
- Monitor guardrail usage patterns

### For Growing Organizations
- Current configuration provides best cost efficiency
- Consider reserved capacity for predictable workloads
- Implement comprehensive monitoring and alerting

## Frequently Asked Questions

### Q: Are there any setup costs?
**A:** No setup costs. You only pay for AWS resources used after deployment.

### Q: Can I reduce costs further?
**A:** Yes, you can disable provisioned concurrency for lower traffic scenarios, reduce log retention, or adjust guardrail settings.

### Q: What happens if I exceed the estimates?
**A:** Costs scale linearly with usage. Set up CloudWatch billing alerts to monitor spending.

### Q: Are there any hidden fees?
**A:** No hidden fees. All costs are transparent AWS service charges based on actual usage.

### Q: Can I get a cost breakdown for my specific use case?
**A:** Yes, the solution includes CloudWatch dashboards that show real-time cost breakdowns by service.

---

*Pricing estimates based on AWS pricing as of January 2025 and standardized usage patterns (15 interactions per user per day, 400 tokens per interaction). Actual costs may vary based on your specific usage patterns and AWS region.*
