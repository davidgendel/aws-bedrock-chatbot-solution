"""
Hybrid Search: Semantic + Keyword Matching

Combines dense vector embeddings with sparse keyword search using BM25/TF-IDF.
Default weighting: 70% semantic + 30% keyword matching.
"""

import logging
import re
import math
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional, Tuple
import json
import os

# Handle both relative and absolute imports
try:
    from .s3_vector_utils import query_similar_vectors
except ImportError:
    from s3_vector_utils import query_similar_vectors

logger = logging.getLogger(__name__)

class BM25Scorer:
    """BM25 keyword scoring implementation."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1  # Term frequency saturation parameter
        self.b = b    # Length normalization parameter
        self.doc_freqs = defaultdict(int)  # Document frequency for each term
        self.doc_lengths = {}  # Document lengths
        self.avg_doc_length = 0.0
        self.total_docs = 0
        
    def preprocess_text(self, text: str) -> List[str]:
        """Preprocess text into tokens."""
        # Convert to lowercase and extract words
        text = text.lower()
        # Remove punctuation and split on whitespace
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def add_document(self, doc_id: str, text: str) -> None:
        """Add document to BM25 index."""
        tokens = self.preprocess_text(text)
        self.doc_lengths[doc_id] = len(tokens)
        
        # Count unique terms in document
        unique_terms = set(tokens)
        for term in unique_terms:
            self.doc_freqs[term] += 1
        
        self.total_docs += 1
        self._update_avg_length()
    
    def _update_avg_length(self) -> None:
        """Update average document length."""
        if self.total_docs > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.total_docs
    
    def score_document(self, query_terms: List[str], doc_id: str, doc_text: str) -> float:
        """Calculate BM25 score for document given query terms."""
        if doc_id not in self.doc_lengths:
            # Add document if not in index
            self.add_document(doc_id, doc_text)
        
        doc_tokens = self.preprocess_text(doc_text)
        doc_length = len(doc_tokens)
        
        # Count term frequencies in document
        term_freqs = Counter(doc_tokens)
        
        score = 0.0
        for term in query_terms:
            if term in term_freqs:
                tf = term_freqs[term]
                df = self.doc_freqs.get(term, 0)
                
                if df > 0:
                    # IDF component
                    idf = math.log((self.total_docs - df + 0.5) / (df + 0.5))
                    
                    # TF component with length normalization
                    tf_component = (tf * (self.k1 + 1)) / (
                        tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
                    )
                    
                    score += idf * tf_component
        
        return max(0.0, score)

class HybridSearcher:
    """Hybrid search combining semantic and keyword matching."""
    
    def __init__(self, semantic_weight: float = 0.7, keyword_weight: float = 0.3):
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.bm25 = BM25Scorer()
        
    def search(
        self,
        query_embedding: List[float],
        query_text: str,
        limit: int = 5,
        semantic_threshold: float = 0.3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword matching.
        
        Args:
            query_embedding: Query vector embedding
            query_text: Original query text for keyword matching
            limit: Number of results to return
            semantic_threshold: Minimum semantic similarity threshold
            filters: Optional metadata filters
        
        Returns:
            List of documents with hybrid scores
        """
        try:
            # Get semantic results with expanded limit for better keyword matching
            expanded_limit = min(limit * 3, 50)  # Get more candidates for keyword scoring
            
            semantic_results = query_similar_vectors(
                query_embedding=query_embedding,
                limit=expanded_limit,
                similarity_threshold=semantic_threshold,
                filters=filters
            )
            
            if not semantic_results:
                logger.warning("No semantic results found")
                return []
            
            # Preprocess query for keyword matching
            query_terms = self.bm25.preprocess_text(query_text)
            if not query_terms:
                logger.warning("No query terms extracted for keyword matching")
                return semantic_results[:limit]
            
            # Calculate hybrid scores
            hybrid_results = []
            
            for doc in semantic_results:
                # Get document text for keyword scoring
                doc_text = self._extract_document_text(doc)
                doc_id = f"{doc.get('document_id', '')}_{doc.get('chunk_index', 0)}"
                
                # Calculate keyword score
                keyword_score = self.bm25.score_document(query_terms, doc_id, doc_text)
                
                # Normalize keyword score (simple min-max normalization)
                # BM25 scores can vary widely, so we use a heuristic normalization
                normalized_keyword_score = min(1.0, keyword_score / 10.0)
                
                # Get semantic score
                semantic_score = doc.get('similarity', 0.0)
                
                # Calculate hybrid score
                hybrid_score = (
                    self.semantic_weight * semantic_score +
                    self.keyword_weight * normalized_keyword_score
                )
                
                # Add scoring metadata
                doc['hybrid_score'] = hybrid_score
                doc['semantic_score'] = semantic_score
                doc['keyword_score'] = normalized_keyword_score
                doc['search_type'] = 'hybrid'
                
                hybrid_results.append(doc)
            
            # Sort by hybrid score and return top results
            hybrid_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
            
            logger.info(f"Hybrid search: {len(hybrid_results)} results, top score: {hybrid_results[0]['hybrid_score']:.3f}")
            
            return hybrid_results[:limit]
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            # Fallback to semantic-only search
            return query_similar_vectors(
                query_embedding=query_embedding,
                limit=limit,
                similarity_threshold=semantic_threshold,
                filters=filters
            )
    
    def _extract_document_text(self, doc: Dict[str, Any]) -> str:
        """Extract searchable text from document."""
        text_parts = []
        
        # Add content
        content = doc.get('content', '')
        if content:
            text_parts.append(content)
        
        # Add heading
        heading = doc.get('heading', '')
        if heading:
            text_parts.append(heading)
        
        # Add document ID as searchable text
        doc_id = doc.get('document_id', '')
        if doc_id:
            text_parts.append(doc_id)
        
        return ' '.join(text_parts)

def hybrid_search(
    query_embedding: List[float],
    query_text: str,
    limit: int = 5,
    semantic_threshold: float = 0.3,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function for hybrid search.
    
    Args:
        query_embedding: Query vector embedding
        query_text: Original query text
        limit: Number of results to return
        semantic_threshold: Minimum semantic similarity
        semantic_weight: Weight for semantic scoring (0-1)
        keyword_weight: Weight for keyword scoring (0-1)
        filters: Optional metadata filters
    
    Returns:
        List of documents with hybrid scores
    """
    # Normalize weights
    total_weight = semantic_weight + keyword_weight
    if total_weight > 0:
        semantic_weight = semantic_weight / total_weight
        keyword_weight = keyword_weight / total_weight
    else:
        semantic_weight, keyword_weight = 0.7, 0.3
    
    searcher = HybridSearcher(semantic_weight, keyword_weight)
    return searcher.search(
        query_embedding=query_embedding,
        query_text=query_text,
        limit=limit,
        semantic_threshold=semantic_threshold,
        filters=filters
    )

def load_hybrid_config() -> Dict[str, Any]:
    """Load hybrid search configuration."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get('hybrid_search', {})
    except Exception as e:
        logger.warning(f"Could not load hybrid search config: {e}, using defaults")
        return {}
