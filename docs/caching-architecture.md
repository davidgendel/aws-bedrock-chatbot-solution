# **Enhanced Caching Architecture**

## **Overview**

The chatbot implements a comprehensive 3-level caching architecture to optimize performance and reduce costs:

1. **Client-Side Caching** (Widget localStorage)
2. **Lambda Memory Caching** (Multi-tier in-memory)
3. **Bedrock Native Caching** (AWS prompt caching)

## **🔧 Implementation Details**

### **Level 1: Client-Side Widget Caching**

**Location**: `src/frontend/widget.js`

**Features**:
- localStorage-based caching with 8-hour TTL
- Maximum 20 cached entries
- Automatic cache expiration and cleanup
- Visual indicators for cached responses

**Configuration**:
```javascript
cache: {
  enabled: true,
  maxEntries: 20,
  ttl: 28800000 // 8 hours
}
```

### **Level 2: Lambda Memory Caching**

**Location**: `lambda_function/cache_manager.py`

**Cache Types**:
- `RESPONSE` - Chat responses (TTL: 2h, Size: 500)
- `VECTOR_QUERY` - Vector similarity queries (TTL: 2h, Size: 200)
- `EMBEDDING` - Document embeddings (LRU, Size: 1000)
- `METADATA` - Document metadata (TTL: 2h, Size: 100)
- `CONFIG` - Configuration data (TTL: 2h, Size: 10)
- `PROMPT` - Bedrock prompt responses (TTL: 1h, Size: 500)
- `CONTEXT` - Retrieved document context (TTL: 2h, Size: 300)
- `GUARDRAIL` - Guardrail results (TTL: 2h, Size: 1000)

### **Level 3: Bedrock Native Caching**

**Location**: `lambda_function/bedrock_utils.py`

**New Features**:

#### **3a. Prompt Caching**
```python
# Cache prompt responses in Lambda memory
prompt_cache = TTLCache(maxsize=500, ttl=3600)  # 1 hour

# Usage
response_result = generate_cached_response(prompt, model_id, use_bedrock_caching=True)
```

#### **3b. Context Caching**
```python
# Cache retrieved document context
context_cache = TTLCache(maxsize=300, ttl=7200)  # 2 hours

# Usage
cached_docs = get_cached_context(embedding, limit=3, threshold=0.7)
if not cached_docs:
    docs = query_similar_vectors(embedding, limit=3, similarity_threshold=0.7)
    cache_context(embedding, limit=3, threshold=0.7, context=docs)
```

#### **3c. AWS Bedrock Native Caching**
```python
# Automatic detection and configuration for supported models
def _supports_bedrock_caching(model_id: str) -> bool:
    supported_models = [
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-3-sonnet-20240229-v1:0",
        "anthropic.claude-3-opus-20240229-v1:0",
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "amazon.nova-micro-v1:0",
        "amazon.nova-lite-v1:0",
        "amazon.nova-pro-v1:0",
        "amazon.nova-premier-v1:0"
         
    ]
    return model_id in supported_models
```

## **🚀 Performance Benefits**

### **Cache Hit Scenarios**

1. **Client Cache Hit**: Instant response (0ms latency)
2. **Lambda Response Cache Hit**: ~50ms response time
3. **Lambda Context Cache Hit**: Eliminates vector search (~200ms saved)
4. **Lambda Prompt Cache Hit**: Eliminates LLM call (~2000ms saved)
5. **Bedrock Native Cache Hit**: Reduced token costs and latency

### **Cost Optimization**

- **Client caching**: Eliminates redundant API calls
- **Context caching**: Reduces vector search operations
- **Prompt caching**: Reduces LLM token consumption
- **Bedrock native caching**: AWS-level optimization for repeated prompts

## **📊 Cache Monitoring**

### **Cache Statistics**

```python
# Get comprehensive cache stats
stats = get_all_bedrock_cache_stats()

# Returns:
{
    "guardrail_cache": {"cache_size": 45, "max_size": 1000, "ttl_seconds": 7200},
    "prompt_cache": {"cache_size": 23, "max_size": 500, "ttl_seconds": 3600},
    "context_cache": {"cache_size": 12, "max_size": 300, "ttl_seconds": 7200},
    "total_cached_items": 80
}
```

### **Cache Management**

```python
# Clear specific caches
clear_prompt_cache()
clear_context_cache()
clear_guardrail_cache()

# Clear all Bedrock caches
clear_all_bedrock_caches()
```

## **🔍 Cache Flow**

### **Chat Request Flow**

1. **Client** checks localStorage → **HIT**: Return cached response
2. **Lambda** checks response cache → **HIT**: Return cached response
3. **Lambda** applies guardrails → **Guardrail cache** → **HIT**: Use cached result
4. **Lambda** generates embeddings → **Embedding cache** → **HIT**: Use cached embeddings
5. **Lambda** queries context → **Context cache** → **HIT**: Use cached context
6. **Lambda** constructs prompt → **Prompt cache** → **HIT**: Return cached response
7. **Bedrock** processes prompt → **Native caching** → **HIT**: Reduced cost/latency

### **Cache Key Generation**

- **Prompt Cache**: SHA256 hash of `prompt:model_id`
- **Context Cache**: SHA256 hash of `embedding_sample:limit:threshold`
- **Guardrail Cache**: MD5 hash of input text

## **⚙️ Configuration**

### **Cache TTL Settings**

```python
# Bedrock caches
guardrail_cache = TTLCache(maxsize=1000, ttl=7200)  # 2 hours
prompt_cache = TTLCache(maxsize=500, ttl=3600)      # 1 hour
context_cache = TTLCache(maxsize=300, ttl=7200)     # 2 hours
```

### **Bedrock Native Caching**

Automatically enabled for:
- RAG prompts with context
- Claude 3 family models
- Amazon Nova family models
- Prompts with system messages

## **🔧 Usage Examples**

### **Basic Usage**

```python
# Generate response with all caching layers
response_result = generate_cached_response(
    prompt="What is AWS Lambda?",
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    use_bedrock_caching=True
)

print(f"Response: {response_result['response']}")
print(f"Cached: {response_result['cached']}")
print(f"Cache Type: {response_result['cache_type']}")
print(f"Bedrock Cached: {response_result['bedrock_cached']}")
```

### **Context Caching**

```python
# Check for cached context first
embedding = generate_embeddings("What is serverless?")
cached_docs = get_cached_context(embedding, limit=3, threshold=0.7)

if cached_docs:
    print("Using cached document context")
    relevant_docs = cached_docs
else:
    print("Fetching new context")
    relevant_docs = query_similar_vectors(embedding, limit=3, similarity_threshold=0.7)
    cache_context(embedding, limit=3, threshold=0.7, context=relevant_docs)
```

## **📈 Expected Performance Improvements**

- **Response Time**: 60-80% reduction for cached responses
- **Token Costs**: 40-60% reduction with prompt caching
- **Vector Search**: 90% reduction with context caching
- **API Calls**: 70% reduction with client-side caching

## **🔍 Debugging**

### **Cache Logging**

Enable debug logging to see cache hit/miss information:

```python
import logging
logging.getLogger('bedrock_utils').setLevel(logging.DEBUG)
```

### **Cache Inspection**

```python
# Check cache contents
print(f"Prompt cache size: {len(prompt_cache)}")
print(f"Context cache size: {len(context_cache)}")
print(f"Guardrail cache size: {len(guardrail_cache)}")
```

This enhanced caching architecture provides comprehensive optimization across all layers of the chatbot system, significantly improving performance while reducing operational costs.
