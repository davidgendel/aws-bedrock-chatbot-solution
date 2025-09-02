"""
Multi-Stage Retrieval with Re-ranking

Implements a two-stage retrieval process:
1. Stage 1: Cast wider net with lower threshold
2. Stage 2: Re-rank using advanced scoring and query analysis
"""

import logging
import re
import json
import os
from typing import List, Dict, Any, Optional, Tuple

# Handle both relative and absolute imports
try:
    from .s3_vector_utils import query_similar_vectors
    from .hybrid_search import hybrid_search, load_hybrid_config
except ImportError:
    from s3_vector_utils import query_similar_vectors
    from hybrid_search import hybrid_search, load_hybrid_config

logger = logging.getLogger(__name__)

def _load_config() -> Dict[str, Any]:
    """Load retrieval configuration."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get('retrieval', {})
    except Exception as e:
        logger.warning(f"Could not load retrieval config: {e}, using defaults")
        return {}

class QueryAnalyzer:
    """Analyzes query complexity and type to determine retrieval strategy."""
    
    @staticmethod
    def analyze_query(query: str) -> Dict[str, Any]:
        """Analyze query to determine complexity and type."""
        query_lower = query.lower().strip()
        
        # Query complexity indicators
        word_count = len(query.split())
        has_questions = bool(re.search(r'\?', query))
        has_specifics = bool(re.search(r'\b(who|what|when|where|why|how)\b', query_lower))
        has_comparisons = bool(re.search(r'\b(compare|versus|vs|difference|similar|like)\b', query_lower))
        has_temporal = bool(re.search(r'\b(before|after|during|when|time|date|year)\b', query_lower))
        has_entities = bool(re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query))
        
        # Determine query type
        query_type = "general"
        if has_specifics:
            query_type = "specific"
        elif has_comparisons:
            query_type = "comparative"
        elif has_temporal:
            query_type = "temporal"
        
        # Calculate complexity score (0-1)
        complexity_score = min(1.0, (
            (word_count / 20.0) * 0.3 +
            (1.0 if has_questions else 0.0) * 0.2 +
            (1.0 if has_specifics else 0.0) * 0.2 +
            (1.0 if has_comparisons else 0.0) * 0.15 +
            (1.0 if has_temporal else 0.0) * 0.1 +
            (1.0 if has_entities else 0.0) * 0.05
        ))
        
        return {
            "type": query_type,
            "complexity": complexity_score,
            "word_count": word_count,
            "has_questions": has_questions,
            "has_specifics": has_specifics,
            "has_comparisons": has_comparisons,
            "has_temporal": has_temporal,
            "has_entities": has_entities
        }

class CrossEncoder:
    """Simple cross-encoder for re-ranking retrieved documents."""
    
    @staticmethod
    def score_relevance(query: str, document: Dict[str, Any], query_analysis: Dict[str, Any]) -> float:
        """Score document relevance using multiple factors."""
        content = document.get("content", "").lower()
        query_lower = query.lower()
        
        # Base similarity score
        base_score = document.get("similarity", 0.0)
        
        # Keyword matching boost
        query_words = set(query_lower.split())
        content_words = set(content.split())
        keyword_overlap = len(query_words.intersection(content_words)) / max(len(query_words), 1)
        keyword_boost = keyword_overlap * 0.2
        
        # Query type specific boosts
        type_boost = 0.0
        if query_analysis["type"] == "specific" and query_analysis["has_entities"]:
            # Boost documents with proper nouns for specific queries
            if re.search(r'\b[A-Z][a-z]+\b', document.get("content", "")):
                type_boost += 0.1
        
        if query_analysis["type"] == "comparative":
            # Boost documents with comparative language
            if re.search(r'\b(than|more|less|better|worse|similar|different)\b', content):
                type_boost += 0.15
        
        if query_analysis["type"] == "temporal":
            # Boost documents with temporal indicators
            if re.search(r'\b(year|time|date|before|after|during|when)\b', content):
                type_boost += 0.1
        
        # Document quality indicators
        quality_boost = 0.0
        importance_score = document.get("importance_score", 1.0)
        if importance_score > 1.2:
            quality_boost += 0.05
        
        # Content length penalty for very short or very long content
        content_length = len(content.split())
        if 50 <= content_length <= 300:  # Optimal range
            quality_boost += 0.05
        elif content_length < 20:  # Too short
            quality_boost -= 0.1
        
        # Combine all factors
        final_score = base_score + keyword_boost + type_boost + quality_boost
        return min(1.0, max(0.0, final_score))

def multi_stage_retrieval(
    query_embedding: List[float],
    query_text: str,
    target_results: int = 3,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Perform multi-stage retrieval with re-ranking.
    
    Args:
        query_embedding: Query vector embedding
        query_text: Original query text for analysis
        target_results: Final number of results to return
        filters: Optional metadata filters
    
    Returns:
        Re-ranked list of relevant documents
    """
    try:
        # Load configuration
        config = _load_config()
        hybrid_config = load_hybrid_config()
        
        # Check if hybrid search is enabled
        use_hybrid = hybrid_config.get('enabled', True)
        
        # Analyze query to determine strategy
        query_analysis = QueryAnalyzer.analyze_query(query_text)
        logger.info(f"Query analysis: type={query_analysis['type']}, complexity={query_analysis['complexity']:.2f}")
        
        # Determine complexity category
        if query_analysis["complexity"] > 0.7:
            complexity_category = "complex"
        elif query_analysis["complexity"] > 0.4:
            complexity_category = "medium"
        else:
            complexity_category = "simple"
        
        # Get thresholds and limits from config
        thresholds = config.get('thresholds', {})
        limits = config.get('limits', {})
        
        # Stage 1 parameters with config defaults
        stage1_threshold = thresholds.get(complexity_category, {}).get('stage1', {
            'simple': 0.4, 'medium': 0.35, 'complex': 0.25
        }[complexity_category])
        
        expansion_multiplier = limits.get('expansionMultiplier', {}).get(complexity_category, {
            'simple': 2, 'medium': 3, 'complex': 4
        }[complexity_category])
        
        stage1_limit = target_results * expansion_multiplier
        
        # Adjust for specific query types
        if query_analysis["type"] == "comparative":
            stage1_limit = max(stage1_limit, target_results * 3)
            stage1_threshold = min(stage1_threshold, 0.3)
        elif query_analysis["type"] == "specific" and query_analysis["has_entities"]:
            stage1_threshold = max(stage1_threshold, 0.4)  # Higher precision for specific queries
        
        logger.info(f"Stage 1: threshold={stage1_threshold}, limit={stage1_limit}, category={complexity_category}, hybrid={use_hybrid}")
        
        # Stage 1: Retrieve candidates using hybrid or semantic search
        if use_hybrid:
            candidates = hybrid_search(
                query_embedding=query_embedding,
                query_text=query_text,
                limit=stage1_limit,
                semantic_threshold=stage1_threshold,
                semantic_weight=hybrid_config.get('semantic_weight', 0.7),
                keyword_weight=hybrid_config.get('keyword_weight', 0.3),
                filters=filters
            )
        else:
            candidates = query_similar_vectors(
                query_embedding=query_embedding,
                limit=stage1_limit,
                similarity_threshold=stage1_threshold,
                filters=filters
            )
        
        if not candidates:
            logger.warning("No candidates found in stage 1, trying lower threshold")
            # Fallback with even lower threshold
            fallback_threshold = max(0.15, stage1_threshold - 0.1)
            if use_hybrid:
                candidates = hybrid_search(
                    query_embedding=query_embedding,
                    query_text=query_text,
                    limit=stage1_limit,
                    semantic_threshold=fallback_threshold,
                    semantic_weight=hybrid_config.get('semantic_weight', 0.7),
                    keyword_weight=hybrid_config.get('keyword_weight', 0.3),
                    filters=filters
                )
            else:
                candidates = query_similar_vectors(
                    query_embedding=query_embedding,
                    limit=stage1_limit,
                    similarity_threshold=fallback_threshold,
                    filters=filters
                )
        
        if not candidates:
            logger.warning("No candidates found even with fallback threshold")
            return []
        
        logger.info(f"Stage 1 retrieved {len(candidates)} candidates")
        
        # Stage 2: Re-rank using cross-encoder (if not already hybrid scored)
        cross_encoder = CrossEncoder()
        
        # Score each candidate
        for candidate in candidates:
            # Use hybrid score if available, otherwise calculate cross-encoder score
            if 'hybrid_score' in candidate:
                # Already has hybrid scoring, use it as base
                candidate["rerank_score"] = candidate['hybrid_score']
            else:
                # Apply cross-encoder scoring
                candidate["rerank_score"] = cross_encoder.score_relevance(
                    query_text, candidate, query_analysis
                )
        
        # Sort by re-ranking score
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        # Apply final threshold based on re-ranking scores
        final_threshold = _determine_final_threshold(candidates, query_analysis, config)
        final_results = [
            doc for doc in candidates 
            if doc["rerank_score"] >= final_threshold
        ][:target_results]
        
        # Ensure we have at least one result if candidates exist
        if not final_results and candidates:
            final_results = candidates[:1]
        
        logger.info(f"Stage 2 re-ranking: {len(final_results)} final results")
        
        # Add retrieval metadata
        for result in final_results:
            result["retrieval_stage"] = "multi_stage"
            result["original_similarity"] = result.get("similarity", 0.0)
            result["similarity"] = result["rerank_score"]  # Use re-rank score as final similarity
            result["query_complexity"] = complexity_category
            result["search_method"] = "hybrid" if use_hybrid else "semantic"
            
            # Preserve hybrid search metadata if available
            if 'hybrid_score' in result:
                result["hybrid_metadata"] = {
                    "semantic_score": result.get("semantic_score", 0.0),
                    "keyword_score": result.get("keyword_score", 0.0),
                    "semantic_weight": hybrid_config.get('semantic_weight', 0.7),
                    "keyword_weight": hybrid_config.get('keyword_weight', 0.3)
                }
        
        return final_results
        
    except Exception as e:
        logger.error(f"Multi-stage retrieval failed: {e}")
        # Fallback to single-stage retrieval
        return query_similar_vectors(
            query_embedding=query_embedding,
            limit=target_results,
            similarity_threshold=0.45,
            filters=filters
        )

def _determine_final_threshold(candidates: List[Dict[str, Any]], query_analysis: Dict[str, Any], config: Dict[str, Any]) -> float:
    """Determine final threshold based on candidate scores and query analysis."""
    if not candidates:
        return 0.0
    
    scores = [doc["rerank_score"] for doc in candidates]
    
    # Determine complexity category
    if query_analysis["complexity"] > 0.7:
        complexity_category = "complex"
    elif query_analysis["complexity"] > 0.4:
        complexity_category = "medium"
    else:
        complexity_category = "simple"
    
    # Get base threshold from config
    thresholds = config.get('thresholds', {})
    base_threshold = thresholds.get(complexity_category, {}).get('final', {
        'simple': 0.4, 'medium': 0.4, 'complex': 0.3
    }[complexity_category])
    
    # Adjust for specific query types
    if query_analysis["type"] == "specific":
        base_threshold = max(base_threshold, 0.5)  # Higher precision for specific queries
    
    # Adaptive threshold based on score distribution
    if len(scores) >= 3:
        top_score = scores[0]
        third_score = scores[2]
        
        # If there's a clear quality gap, use it
        if top_score - third_score > 0.2:
            adaptive_threshold = third_score + 0.05
        else:
            adaptive_threshold = base_threshold
    else:
        adaptive_threshold = base_threshold
    
    return min(base_threshold, adaptive_threshold)

# Convenience function for backward compatibility
def enhanced_query_similar_vectors(
    query_embedding: List[float],
    query_text: str = "",
    limit: int = 3,
    similarity_threshold: float = 0.45,
    filters: Optional[Dict[str, Any]] = None,
    use_multi_stage: bool = None
) -> List[Dict[str, Any]]:
    """
    Vector query with optional multi-stage retrieval.
    
    Args:
        query_embedding: Query vector embedding
        query_text: Original query text (required for multi-stage)
        limit: Number of results to return
        similarity_threshold: Minimum similarity (used only for single-stage)
        filters: Optional metadata filters
        use_multi_stage: Whether to use multi-stage retrieval (None = use config)
    
    Returns:
        List of relevant documents
    """
    # Load configuration to determine if multi-stage is enabled
    if use_multi_stage is None:
        config = _load_config()
        use_multi_stage = config.get('multiStage', {}).get('enabled', True)
    
    if use_multi_stage and query_text:
        try:
            return multi_stage_retrieval(
                query_embedding=query_embedding,
                query_text=query_text,
                target_results=limit,
                filters=filters
            )
        except Exception as e:
            logger.error(f"Multi-stage retrieval failed: {e}")
            # Check if fallback is enabled
            config = _load_config()
            if config.get('multiStage', {}).get('fallbackToSingleStage', True):
                logger.info("Falling back to single-stage retrieval")
                return query_similar_vectors(
                    query_embedding=query_embedding,
                    limit=limit,
                    similarity_threshold=similarity_threshold,
                    filters=filters
                )
            else:
                raise
    else:
        # Use original single-stage retrieval
        return query_similar_vectors(
            query_embedding=query_embedding,
            limit=limit,
            similarity_threshold=similarity_threshold,
            filters=filters
        )
