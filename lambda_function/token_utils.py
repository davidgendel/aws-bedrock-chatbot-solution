"""
Token utilities for optimizing prompts and managing token usage.
"""
import re
from typing import Dict, Any, Optional


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text string.
    This is a rough approximation based on character count.
    
    Args:
        text: The input text
        
    Returns:
        Estimated token count
    """
    # A very rough approximation: 1 token ≈ 4 characters for English text
    return len(text) // 4


def calculate_token_cost(input_tokens: int, output_tokens: int, model_id: str) -> float:
    """
    Calculate the cost of token usage based on AWS Bedrock pricing.
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model_id: Model identifier
        
    Returns:
        Estimated cost in USD
    """
    # AWS Bedrock pricing (as of 2024)
    pricing = {
        'amazon.nova-lite-v1:0': {
            'input_tokens_per_1k': 0.00006,  # $0.00006 per 1K input tokens
            'output_tokens_per_1k': 0.00024,  # $0.00024 per 1K output tokens
        },
        'amazon.nova-micro-v1:0': {
            'input_tokens_per_1k': 0.000035,  # $0.000035 per 1K input tokens
            'output_tokens_per_1k': 0.00014,  # $0.00014 per 1K output tokens
        },
        'amazon.titan-embed-text-v1': {
            'input_tokens_per_1k': 0.0001,  # $0.0001 per 1K tokens
            'output_tokens_per_1k': 0.0,  # No output tokens for embeddings
        },
        'anthropic.claude-3-haiku-20240307-v1:0': {
            'input_tokens_per_1k': 0.00025,  # $0.00025 per 1K input tokens
            'output_tokens_per_1k': 0.00125,  # $0.00125 per 1K output tokens
        }
    }
    
    model_pricing = pricing.get(model_id, pricing['amazon.nova-lite-v1:0'])  # Default to Nova Lite
    
    input_cost = (input_tokens / 1000) * model_pricing['input_tokens_per_1k']
    output_cost = (output_tokens / 1000) * model_pricing['output_tokens_per_1k']
    
    return input_cost + output_cost


def get_model_cost_info(model_id: str) -> Dict[str, Any]:
    """
    Get cost information for a specific model.
    
    Args:
        model_id: Model identifier
        
    Returns:
        Dictionary with cost information
    """
    pricing = {
        'amazon.nova-lite-v1:0': {
            'input_cost_per_1k': 0.00006,
            'output_cost_per_1k': 0.00024,
            'description': 'Amazon Nova Lite - Fast and cost-effective',
            'use_case': 'General chat and Q&A'
        },
        'amazon.nova-micro-v1:0': {
            'input_cost_per_1k': 0.000035,
            'output_cost_per_1k': 0.00014,
            'description': 'Amazon Nova Micro - Ultra low cost',
            'use_case': 'Simple tasks and high-volume scenarios'
        },
        'amazon.titan-embed-text-v1': {
            'input_cost_per_1k': 0.0001,
            'output_cost_per_1k': 0.0,
            'description': 'Amazon Titan Embeddings - Text embeddings',
            'use_case': 'Document embeddings and similarity search'
        }
    }
    
    return pricing.get(model_id, {
        'input_cost_per_1k': 0.0001,
        'output_cost_per_1k': 0.0005,
        'description': 'Unknown model',
        'use_case': 'General purpose'
    })


def estimate_conversation_cost(
    messages: list,
    model_id: str,
    include_context: bool = True
) -> Dict[str, Any]:
    """
    Estimate the cost of a conversation.
    
    Args:
        messages: List of messages in the conversation
        model_id: Model identifier
        include_context: Whether to include RAG context in estimation
        
    Returns:
        Dictionary with cost estimation details
    """
    total_input_tokens = 0
    total_output_tokens = 0
    
    for message in messages:
        if isinstance(message, dict):
            # Handle structured messages
            if message.get('role') == 'user':
                total_input_tokens += estimate_tokens(message.get('content', ''))
            elif message.get('role') == 'assistant':
                total_output_tokens += estimate_tokens(message.get('content', ''))
        else:
            # Handle simple string messages
            total_input_tokens += estimate_tokens(str(message))
    
    # Add estimated context tokens if RAG is used
    if include_context:
        # Estimate 500-1000 tokens for RAG context per query
        context_tokens_per_message = 750
        user_messages = len([m for m in messages if (isinstance(m, dict) and m.get('role') == 'user') or isinstance(m, str)])
        total_input_tokens += context_tokens_per_message * user_messages
    
    total_cost = calculate_token_cost(total_input_tokens, total_output_tokens, model_id)
    
    return {
        'total_input_tokens': total_input_tokens,
        'total_output_tokens': total_output_tokens,
        'total_tokens': total_input_tokens + total_output_tokens,
        'estimated_cost': round(total_cost, 6),
        'model_id': model_id,
        'includes_rag_context': include_context,
        'cost_breakdown': {
            'input_cost': round((total_input_tokens / 1000) * get_model_cost_info(model_id)['input_cost_per_1k'], 6),
            'output_cost': round((total_output_tokens / 1000) * get_model_cost_info(model_id)['output_cost_per_1k'], 6)
        }
    }


def optimize_prompt(prompt: str, max_tokens: int = 4000) -> str:
    """
    Optimize a prompt to reduce token usage while preserving important content.
    
    Args:
        prompt: The input prompt
        max_tokens: Maximum number of tokens allowed
        
    Returns:
        Optimized prompt
    """
    estimated_tokens = estimate_tokens(prompt)
    
    # If already under the limit, return as is
    if estimated_tokens <= max_tokens:
        return prompt
    
    # Split the prompt into sections
    sections = re.split(r'\n\n+', prompt)
    
    # Identify the user question (usually at the end)
    user_question = None
    for i in range(len(sections) - 1, -1, -1):
        if sections[i].lower().startswith('user question:'):
            user_question = sections[i]
            sections.pop(i)
            break
    
    # Identify the context section
    context_start = -1
    context_end = -1
    for i, section in enumerate(sections):
        if section.startswith('Here is some relevant information'):
            context_start = i
        elif context_start >= 0 and section.strip() == '':
            context_end = i
            break
    
    # If we found the context section
    if context_start >= 0:
        context_sections = sections[context_start:context_end] if context_end > 0 else sections[context_start:]
        other_sections = sections[:context_start] + (sections[context_end:] if context_end > 0 else [])
        
        # Calculate tokens for non-context parts
        other_text = '\n\n'.join(other_sections)
        other_tokens = estimate_tokens(other_text)
        
        # Calculate available tokens for context
        available_context_tokens = max_tokens - other_tokens
        if user_question:
            available_context_tokens -= estimate_tokens(user_question)
        
        # If we need to reduce context
        if available_context_tokens < estimate_tokens('\n\n'.join(context_sections)):
            # Extract individual documents from context
            documents = []
            current_doc = []
            
            for line in '\n\n'.join(context_sections).split('\n'):
                if line.startswith('Document '):
                    if current_doc:
                        documents.append('\n'.join(current_doc))
                    current_doc = [line]
                else:
                    current_doc.append(line)
            
            if current_doc:
                documents.append('\n'.join(current_doc))
            
            # Sort documents by relevance (assuming they're already sorted)
            # Keep adding documents until we hit the token limit
            optimized_context = []
            current_tokens = 0
            
            for doc in documents:
                doc_tokens = estimate_tokens(doc)
                if current_tokens + doc_tokens <= available_context_tokens:
                    optimized_context.append(doc)
                    current_tokens += doc_tokens
                else:
                    break
            
            # Rebuild the prompt
            result = []
            if context_start > 0:
                result.extend(sections[:context_start])
            
            if optimized_context:
                result.append('Here is some relevant information that might help answer the question:')
                result.extend(optimized_context)
            
            if context_end > 0:
                result.extend(sections[context_end:])
            
            if user_question:
                result.append(user_question)
            
            return '\n\n'.join(result)
    
    # Fallback: simple truncation while preserving the user question
    if user_question:
        # Calculate available tokens for the rest of the prompt
        available_tokens = max_tokens - estimate_tokens(user_question) - 100  # Buffer
        
        # Truncate the rest of the prompt
        rest_of_prompt = '\n\n'.join(sections)
        truncated_prompt = rest_of_prompt[:available_tokens * 4]  # Convert back to characters
        
        return truncated_prompt + '\n\n' + user_question
    
    # Last resort: just truncate
    return prompt[:max_tokens * 4]  # Convert tokens to approximate characters
