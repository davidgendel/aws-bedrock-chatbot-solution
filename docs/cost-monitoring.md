# 💰 Cost Monitoring Guide

This guide covers the comprehensive cost monitoring system implemented in the RAG chatbot solution.

## 🚀 Overview

The cost monitoring system provides real-time tracking and analysis of:
- **Token Usage**: Input/output tokens for all Bedrock models
- **Vector Operations**: S3 Vector queries and storage costs
- **Cache Performance**: Hit rates and cost savings
- **API Calls**: Duration and frequency of AWS service calls
- **Conversation Costs**: Per-conversation cost attribution

## 🏗️ Architecture

### Core Components

1. **CostMonitor**: Centralized cost tracking and calculation
2. **MetricsCollector**: Batching and CloudWatch publishing
3. **CloudWatch Dashboard**: Real-time cost visualization
4. **Cost Alarms**: Automated cost threshold alerts

### Data Flow

```
Lambda Function → CostMonitor → MetricsCollector → CloudWatch → Dashboard
```

## ⚙️ Configuration

### Basic Configuration

Edit `config.json` to configure cost monitoring:

```json
{
  "costMonitoring": {
    "enabled": true,
    "cloudWatchNamespace": "Chatbot/Costs",
    "batchSize": 20,
    "flushInterval": 60,
    "trackConversationCosts": true,
    "enableDetailedMetrics": true,
    "costAlerts": {
      "enabled": true,
      "dailyThreshold": 5.0,
      "monthlyThreshold": 100.0,
      "conversationThreshold": 0.10
    }
  }
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable/disable cost monitoring | `true` |
| `cloudWatchNamespace` | CloudWatch metrics namespace | `"Chatbot/Costs"` |
| `batchSize` | Metrics batch size for CloudWatch | `20` |
| `flushInterval` | Metrics flush interval (seconds) | `60` |
| `trackConversationCosts` | Track per-conversation costs | `true` |
| `enableDetailedMetrics` | Enable detailed metric collection | `true` |

## 📊 Metrics Collected

### Token Usage Metrics

- **MetricName**: `TokenUsage`
- **Unit**: `Count`
- **Dimensions**: `ModelId`, `Cached`, `ConversationId`
- **Description**: Total tokens used per request

### Cost Metrics

- **MetricName**: `ConversationCost`
- **Unit**: `USD`
- **Dimensions**: `ModelId`, `ConversationId`
- **Description**: Estimated cost per conversation

### Cache Performance Metrics

- **MetricName**: `CacheHit` / `CacheMiss`
- **Unit**: `Count`
- **Dimensions**: `CacheType`, `ConversationId`
- **Description**: Cache hit/miss rates by type

### Vector Query Metrics

- **MetricName**: `VectorQuery`
- **Unit**: `Count`
- **Dimensions**: `CacheHit`, `VectorsSearched`, `ConversationId`
- **Description**: S3 Vector query operations

### API Call Metrics

- **MetricName**: `APICall`
- **Unit**: `Count` / `Milliseconds`
- **Dimensions**: `APIType`, `ConversationId`
- **Description**: AWS API call frequency and duration

## 💡 Usage Examples

### Basic Cost Tracking

```python
from cost_monitor import track_tokens, track_vector_query, track_cache_hit

# Track token usage
token_usage = track_tokens(
    input_tokens=100,
    output_tokens=50,
    model_id='amazon.nova-lite-v1:0',
    conversation_id='conv-123'
)

# Track vector query
cost = track_vector_query(
    query_count=1,
    vectors_searched=100,
    conversation_id='conv-123'
)

# Track cache hit
track_cache_hit(
    cache_type='response_cache',
    conversation_id='conv-123',
    cost_saved=0.001
)
```

### Getting Cost Summary

```python
from cost_monitor import get_cost_summary, get_cost_monitor

# Get overall cost summary
summary = get_cost_summary()
print(f"Total cost: ${summary['total_cost_estimate']}")
print(f"Cache hit rate: {summary['cache_hit_rate']:.1%}")

# Get conversation-specific costs
cost_monitor = get_cost_monitor()
conv_cost = cost_monitor.get_conversation_cost('conv-123')
if conv_cost:
    print(f"Conversation cost: ${conv_cost.total_cost_estimate:.6f}")
    print(f"Total tokens: {conv_cost.total_tokens}")
```

### Manual Metrics Flushing

```python
from cost_monitor import flush_cost_metrics

# Flush metrics to CloudWatch
success = flush_cost_metrics(force=True)
if success:
    print("Metrics flushed successfully")
```

## 📈 CloudWatch Dashboard

### Accessing the Dashboard

After deployment, access your cost monitoring dashboard at:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=ChatbotCosts-YourStackName
```

### Dashboard Widgets

1. **Token Usage**: Real-time token consumption
2. **Conversation Costs**: Cost trends over time
3. **Cache Hit Rate**: Cache performance metrics
4. **Vector Queries**: S3 Vector operation frequency
5. **API Calls by Type**: Breakdown of AWS service usage

## 🚨 Cost Alerts

### Automatic Alerts

The system creates CloudWatch alarms for:

- **Daily Cost Threshold**: Alert when daily costs exceed limit
- **High Conversation Cost**: Alert for expensive single conversations
- **Monthly Cost Projection**: Estimated monthly cost warnings

### Custom Alerts

Create additional alarms in CloudWatch:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "ChatbotHighTokenUsage" \
  --alarm-description "High token usage detected" \
  --metric-name TokenUsage \
  --namespace Chatbot/Costs \
  --statistic Sum \
  --period 300 \
  --threshold 10000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

## 🔧 Troubleshooting

### Common Issues

**Metrics Not Appearing**
- Check CloudWatch permissions in Lambda role
- Verify `costMonitoring.enabled` is `true` in config
- Check CloudWatch logs for error messages

**High Costs**
- Review cache hit rates - low rates indicate inefficient caching
- Check token usage patterns - optimize prompts if needed
- Monitor vector query frequency - implement better caching

**Dashboard Not Loading**
- Verify CloudWatch dashboard was created during deployment
- Check IAM permissions for CloudWatch access
- Ensure metrics namespace matches configuration

### Debug Commands

```bash
# Check CloudWatch metrics
aws cloudwatch list-metrics --namespace "Chatbot/Costs"

# Get metric statistics
aws cloudwatch get-metric-statistics \
  --namespace "Chatbot/Costs" \
  --metric-name "TokenUsage" \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum

# Check Lambda logs
aws logs filter-log-events \
  --log-group-name "/aws/lambda/ChatbotRag-ChatbotFunction" \
  --filter-pattern "cost"
```

## 💰 Cost Optimization Tips

### Reduce Token Costs

1. **Optimize Prompts**: Use shorter, more focused prompts
2. **Enable Caching**: Ensure response caching is working
3. **Choose Right Model**: Use Nova Micro for simple tasks

### Reduce Vector Costs

1. **Improve Cache Hit Rates**: Optimize similarity thresholds
2. **Batch Queries**: Process multiple queries together
3. **Optimize Index**: Regular vector index optimization

### Monitor and Alert

1. **Set Appropriate Thresholds**: Based on your usage patterns
2. **Regular Review**: Weekly cost analysis
3. **Automated Actions**: Consider Lambda functions for cost control

## 📊 Cost Analysis Queries

### CloudWatch Insights Queries

```sql
-- Top conversations by cost
fields @timestamp, conversationId, cost
| filter @message like /ConversationCost/
| stats sum(cost) as totalCost by conversationId
| sort totalCost desc
| limit 10

-- Cache hit rate analysis
fields @timestamp, cacheType, hit
| filter @message like /Cache/
| stats count() as total, sum(hit) as hits by cacheType
| eval hitRate = hits / total * 100
| sort hitRate desc

-- Token usage by model
fields @timestamp, modelId, tokens
| filter @message like /TokenUsage/
| stats sum(tokens) as totalTokens by modelId
| sort totalTokens desc
```

## 🔮 Advanced Features

### Custom Metrics

Add custom cost metrics:

```python
from cost_monitor import get_cost_monitor

cost_monitor = get_cost_monitor()
cost_monitor.track_api_call(
    api_type='custom_service',
    duration_ms=250,
    conversation_id='conv-123',
    metadata={'custom_field': 'value'}
)
```

### Cost Prediction

Implement cost prediction based on usage patterns:

```python
def predict_monthly_cost(daily_conversations: int, avg_tokens_per_conv: int) -> float:
    """Predict monthly cost based on usage patterns."""
    from token_utils import calculate_token_cost
    
    daily_cost = daily_conversations * calculate_token_cost(
        avg_tokens_per_conv * 0.7,  # Input tokens (70%)
        avg_tokens_per_conv * 0.3,  # Output tokens (30%)
        'amazon.nova-lite-v1:0'
    )
    
    return daily_cost * 30  # Monthly estimate
```

## 📝 Best Practices

1. **Monitor Regularly**: Check dashboard weekly
2. **Set Realistic Thresholds**: Based on actual usage
3. **Optimize Continuously**: Regular performance reviews
4. **Document Changes**: Track optimization efforts
5. **Test Thoroughly**: Validate cost tracking accuracy

---

**Need Help?**

- Check [troubleshooting.md](troubleshooting.md) for common issues
- Review CloudWatch logs for detailed error information
- Monitor the cost dashboard for usage patterns
- Set up appropriate alerts for your use case
