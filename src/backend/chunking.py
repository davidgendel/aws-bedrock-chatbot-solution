"""
Document chunking utilities for the chatbot backend.
"""
import logging
import re
from typing import Any, Dict, List

import nltk
from nltk.tokenize import sent_tokenize

try:
    from .constants import (
        DEFAULT_CHUNK_SIZE, MAX_CHUNK_SIZE, MIN_CHUNK_SIZE, CHUNK_OVERLAP_SIZE
    )
except ImportError:
    from constants import (
        DEFAULT_CHUNK_SIZE, MAX_CHUNK_SIZE, MIN_CHUNK_SIZE, CHUNK_OVERLAP_SIZE
    )

logger = logging.getLogger(__name__)

# Download NLTK data if not already downloaded - support both old and new versions
def ensure_nltk_resources():
    """Ensure required NLTK resources are available."""
    resources_needed = ['punkt_tab', 'punkt']  # Try new version first, fallback to old
    for resource in resources_needed:
        try:
            nltk.data.find(f'tokenizers/{resource}')
            return  # Success, we have what we need
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
                return  # Successfully downloaded
            except:
                continue  # Try next resource
    
    # If we get here, log a warning but continue
    logger.warning("Could not download NLTK punkt resources, sentence tokenization may fail")

# Call the function
ensure_nltk_resources()


def create_chunks(
    content, 
    metadata: Dict[str, Any] = None, 
    max_chunk_size: int = None, 
    overlap_size: int = None
) -> List[Dict[str, Any]]:
    """
    Create chunks using advanced semantic-aware chunking strategies.
    
    Args:
        content: Either extracted content dict or text string
        metadata: Document metadata (optional)
        max_chunk_size: Maximum chunk size override (optional)
        overlap_size: Overlap size override (optional)
        
    Returns:
        List of document chunks
    """
    # Handle both calling patterns
    if isinstance(content, dict):
        text = content["text"]
        structure = content.get("structure", [])
        metadata = content.get("metadata", metadata or {})
    else:
        text = content
        structure = []
        metadata = metadata or {}
    
    # Adaptive configuration based on content analysis
    config = analyze_content_and_configure(text, max_chunk_size, overlap_size)
    
    # Use structure-aware chunking if available, otherwise semantic chunking
    if structure:
        return create_structured_chunks(text, structure, metadata, config)
    else:
        return create_semantic_chunks(text, metadata, config)


def analyze_content_and_configure(text: str, max_chunk_size: int = None, overlap_size: int = None) -> Dict[str, Any]:
    """Analyze content to determine optimal chunking configuration."""
    # Base configuration
    config = {
        "targetChunkSize": DEFAULT_CHUNK_SIZE,
        "maxChunkSize": max_chunk_size or MAX_CHUNK_SIZE,
        "minChunkSize": MIN_CHUNK_SIZE,
        "overlapSize": overlap_size or CHUNK_OVERLAP_SIZE,
        "sentenceEndingChars": ['.', '!', '?', '\n\n']
    }
    
    # Analyze content characteristics
    lines = text.split('\n')
    avg_line_length = sum(len(line) for line in lines) / max(len(lines), 1)
    
    # Detect content type patterns
    dialogue_ratio = len(re.findall(r'"[^"]*"', text)) / max(len(text.split()), 1)
    paragraph_breaks = text.count('\n\n')
    
    # Adjust chunk sizes based on content density
    if dialogue_ratio > 0.1:  # Dialogue-heavy content
        config["targetChunkSize"] = int(config["targetChunkSize"] * 0.8)  # Smaller chunks
        config["overlapSize"] = int(config["overlapSize"] * 1.2)  # More overlap
    elif avg_line_length > 100:  # Dense prose
        config["targetChunkSize"] = int(config["targetChunkSize"] * 1.2)  # Larger chunks
    elif paragraph_breaks > len(lines) * 0.3:  # Well-structured text
        config["targetChunkSize"] = int(config["targetChunkSize"] * 1.1)  # Slightly larger
    
    return config


def create_structured_chunks(
    text: str, structure: List[Dict[str, Any]], metadata: Dict[str, Any], config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Create chunks based on document structure with semantic awareness.
    
    Args:
        text: Document text
        structure: Document structure
        metadata: Document metadata
        config: Chunking configuration
        
    Returns:
        List of document chunks
    """
    chunks = []
    sorted_structure = sorted(structure, key=lambda x: x["startPosition"])
    sorted_structure.append({"startPosition": len(text), "level": 0, "text": "END_OF_DOCUMENT"})
    
    for i in range(len(sorted_structure) - 1):
        current_heading = sorted_structure[i]
        next_heading = sorted_structure[i + 1]
        
        section_start = current_heading["startPosition"]
        section_end = next_heading["startPosition"]
        section_text = text[section_start:section_end].strip()
        
        if not section_text:
            continue
        
        # Determine section importance and adjust chunk size accordingly
        section_importance = calculate_section_importance(current_heading, section_text)
        adjusted_config = adjust_config_for_section(config, section_importance, len(section_text))
        
        if len(section_text) <= adjusted_config["maxChunkSize"]:
            # Keep short sections intact
            chunks.append({
                "content": section_text,
                "type": "section",
                "heading": current_heading["text"],
                "importanceScore": section_importance,
                "metadata": {
                    "headingLevel": current_heading["level"],
                    "sectionIndex": i,
                    "sectionLength": len(section_text),
                    **metadata
                }
            })
        else:
            # Split long sections with semantic awareness
            section_chunks = split_section_semantically(section_text, adjusted_config)
            
            for chunk_index, chunk in enumerate(section_chunks):
                chunk_importance = section_importance * (1.0 - chunk_index * 0.1)  # First chunks more important
                chunks.append({
                    "content": chunk,
                    "type": "section_chunk",
                    "heading": current_heading["text"],
                    "importanceScore": max(chunk_importance, 0.5),
                    "metadata": {
                        "headingLevel": current_heading["level"],
                        "sectionIndex": i,
                        "chunkIndex": chunk_index,
                        "totalChunksInSection": len(section_chunks),
                        **metadata
                    }
                })
    
    return chunks


def calculate_section_importance(heading: Dict[str, Any], text: str) -> float:
    """Calculate importance score for a section based on heading and content."""
    score = 1.0
    
    # Higher score for higher-level headings
    if heading.get("level"):
        score += (7 - min(heading["level"], 6)) * 0.15
    
    # Analyze heading text for importance indicators
    heading_text = ""
    if heading and heading.get("text"):
        heading_text = heading["text"].lower()
    important_keywords = ["introduction", "conclusion", "summary", "overview", "key", "important", "main"]
    if any(keyword in heading_text for keyword in important_keywords):
        score += 0.3
    
    # Analyze content density
    sentences = len(re.findall(r'[.!?]+', text))
    words = len(text.split())
    if words > 0:
        sentence_density = sentences / words * 100
        if 3 <= sentence_density <= 8:  # Good information density
            score += 0.2
    
    return min(score, 2.0)


def adjust_config_for_section(config: Dict[str, Any], importance: float, section_length: int) -> Dict[str, Any]:
    """Adjust chunking configuration based on section characteristics."""
    adjusted = config.copy()
    
    # Important sections get larger chunks to preserve context
    if importance > 1.5:
        adjusted["targetChunkSize"] = int(config["targetChunkSize"] * 1.3)
        adjusted["maxChunkSize"] = int(config["maxChunkSize"] * 1.2)
        adjusted["overlapSize"] = int(config["overlapSize"] * 1.5)
    
    # Very long sections may need smaller chunks for manageability
    elif section_length > config["maxChunkSize"] * 3:
        adjusted["targetChunkSize"] = int(config["targetChunkSize"] * 0.9)
    
    return adjusted


def split_section_semantically(text: str, config: Dict[str, Any]) -> List[str]:
    """Split a section into chunks while preserving semantic boundaries."""
    try:
        sentences = sent_tokenize(text)
    except Exception:
        return split_text_into_chunks(text, config)
    
    # Find natural breakpoints within the section
    breakpoints = detect_semantic_breakpoints(sentences)
    
    chunks = []
    current_chunk = ""
    current_sentences = []
    
    for i, sentence in enumerate(sentences):
        # Check for semantic break
        should_break = (
            i in breakpoints and 
            current_chunk and 
            len(current_chunk) >= config["minChunkSize"]
        )
        
        # Force break if too large
        force_break = len(current_chunk) + len(sentence) > config["maxChunkSize"] and current_chunk
        
        if should_break or force_break:
            chunks.append(current_chunk.strip())
            
            # Preserve context with semantic overlap
            overlap_sentences = get_contextual_overlap(current_sentences, config["overlapSize"], sentence)
            current_chunk = " ".join(overlap_sentences)
            current_sentences = overlap_sentences.copy()
        
        # Add sentence
        if current_chunk:
            current_chunk += " " + sentence
        else:
            current_chunk = sentence
        current_sentences.append(sentence)
    
    # Add final chunk
    if current_chunk.strip():
        if len(current_chunk) >= config["minChunkSize"] or not chunks:
            chunks.append(current_chunk.strip())
        elif chunks:
            chunks[-1] += " " + current_chunk.strip()
    
    return chunks


def get_contextual_overlap(sentences: List[str], overlap_size: int, next_sentence: str) -> List[str]:
    """Get overlap that maintains context continuity."""
    if not sentences:
        return []
    
    # Try to include complete thoughts in overlap
    overlap_sentences = []
    char_count = 0
    
    # Work backwards, but prioritize complete thoughts
    for i in range(len(sentences) - 1, -1, -1):
        sentence = sentences[i]
        if char_count + len(sentence) <= overlap_size:
            overlap_sentences.insert(0, sentence)
            char_count += len(sentence)
            
            # If this sentence provides good context for the next sentence, prefer it
            if has_contextual_connection(sentence, next_sentence):
                break
        else:
            break
    
    return overlap_sentences or [sentences[-1]] if sentences else []


def has_contextual_connection(prev_sentence: str, next_sentence: str) -> bool:
    """Check if two sentences have contextual connection."""
    # Look for pronouns, references, or continuing thoughts
    next_lower = next_sentence.lower()
    
    # Pronouns and references
    references = ['he', 'she', 'it', 'they', 'this', 'that', 'these', 'those']
    if any(next_lower.startswith(ref) for ref in references):
        return True
    
    # Continuing conjunctions
    continuations = ['and', 'but', 'however', 'therefore', 'thus', 'moreover']
    if any(next_lower.startswith(conj) for conj in continuations):
        return True
    
    return False


def create_semantic_chunks(
    text: str, metadata: Dict[str, Any], config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Create semantic chunks without structure information.
    
    Args:
        text: Document text
        metadata: Document metadata
        config: Chunking configuration
        
    Returns:
        List of document chunks
    """
    chunks = []
    
    # Split text into semantic chunks using NLP
    text_chunks = split_text_into_chunks_nlp(text, config)
    
    # Process each chunk
    for index, chunk in enumerate(text_chunks):
        # Try to extract a title from the first chunk
        chunk_title = None
        if index == 0:
            # Look for potential title in the first few lines
            lines = [line for line in chunk.split('\n') if line.strip()]
            if lines and len(lines[0]) < MIN_CHUNK_SIZE:
                chunk_title = lines[0]
        
        chunks.append({
            "content": chunk,
            "type": "text_chunk",
            "heading": chunk_title,
            "importanceScore": 1.0,
            "metadata": {
                "chunkIndex": index,
                **metadata
            }
        })
    
    return chunks


def split_text_into_chunks_nlp(text: str, config: Dict[str, Any]) -> List[str]:
    """
    Split text into chunks at semantic boundaries using advanced NLP techniques.
    
    Args:
        text: Document text
        config: Chunking configuration
        
    Returns:
        List of text chunks
    """
    try:
        sentences = sent_tokenize(text)
    except Exception as e:
        logger.warning(f"NLTK sentence tokenization failed: {e}. Falling back to simple splitting.")
        return split_text_into_chunks(text, config)
    
    # Detect semantic breakpoints
    breakpoints = detect_semantic_breakpoints(sentences)
    
    chunks = []
    current_chunk = ""
    current_sentences = []
    
    for i, sentence in enumerate(sentences):
        # Check if we should break here based on semantic analysis
        should_break = (
            i in breakpoints and 
            current_chunk and 
            len(current_chunk) >= config["minChunkSize"]
        )
        
        # Force break if we exceed max size
        force_break = len(current_chunk) + len(sentence) > config["maxChunkSize"] and current_chunk
        
        if should_break or force_break:
            # Finalize current chunk
            chunks.append(current_chunk.strip())
            
            # Start new chunk with semantic overlap
            overlap_sentences = get_semantic_overlap(current_sentences, config["overlapSize"])
            current_chunk = " ".join(overlap_sentences)
            current_sentences = overlap_sentences.copy()
        
        # Add sentence to current chunk
        if current_chunk:
            current_chunk += " " + sentence
        else:
            current_chunk = sentence
        current_sentences.append(sentence)
        
        # Create chunk if we reach target size and have a good breakpoint
        if (len(current_chunk) >= config["targetChunkSize"] and 
            i + 1 < len(sentences) and 
            is_good_breakpoint(sentence, sentences[i + 1] if i + 1 < len(sentences) else "")):
            chunks.append(current_chunk.strip())
            current_chunk = ""
            current_sentences = []
    
    # Add final chunk
    if current_chunk.strip():
        if len(current_chunk) >= config["minChunkSize"] or not chunks:
            chunks.append(current_chunk.strip())
        elif chunks:
            chunks[-1] += " " + current_chunk.strip()
    
    return chunks


def detect_semantic_breakpoints(sentences: List[str]) -> set:
    """Detect natural breakpoints in text based on semantic cues."""
    breakpoints = set()
    
    for i in range(len(sentences) - 1):
        current = sentences[i].strip()
        next_sent = sentences[i + 1].strip()
        
        # Paragraph breaks (double newlines preserved in sentences)
        if '\n\n' in current or current.endswith('\n'):
            breakpoints.add(i + 1)
        
        # Topic transitions (discourse markers)
        transition_markers = [
            'however', 'meanwhile', 'furthermore', 'moreover', 'nevertheless',
            'in contrast', 'on the other hand', 'in addition', 'consequently',
            'therefore', 'thus', 'as a result', 'in conclusion', 'finally',
            'first', 'second', 'third', 'next', 'then', 'later', 'afterwards'
        ]
        
        next_lower = next_sent.lower()
        if any(next_lower.startswith(marker) for marker in transition_markers):
            breakpoints.add(i + 1)
        
        # Dialogue boundaries
        if (current.endswith('"') or current.endswith("'")) and not next_sent.startswith('"'):
            breakpoints.add(i + 1)
        
        # Time/scene transitions
        time_markers = ['the next day', 'later that', 'meanwhile', 'suddenly', 'then', 'after']
        if any(marker in next_lower[:50] for marker in time_markers):
            breakpoints.add(i + 1)
        
        # Character/speaker changes (common in narratives)
        if (re.match(r'^[A-Z][a-z]+ (said|asked|replied|answered|shouted|whispered)', next_sent) or
            re.match(r'^"[^"]*"[,.]? [A-Z][a-z]+ (said|asked)', next_sent)):
            breakpoints.add(i + 1)
    
    return breakpoints


def get_semantic_overlap(sentences: List[str], overlap_size: int) -> List[str]:
    """Get semantically meaningful overlap sentences."""
    if not sentences or overlap_size <= 0:
        return []
    
    # Calculate how many sentences to include in overlap
    total_chars = sum(len(s) for s in sentences)
    if total_chars <= overlap_size:
        return sentences
    
    # Work backwards to find sentences that fit in overlap_size
    overlap_sentences = []
    char_count = 0
    
    for sentence in reversed(sentences):
        if char_count + len(sentence) <= overlap_size:
            overlap_sentences.insert(0, sentence)
            char_count += len(sentence)
        else:
            break
    
    # Ensure we have at least one sentence if possible
    if not overlap_sentences and sentences:
        overlap_sentences = [sentences[-1]]
    
    return overlap_sentences


def is_good_breakpoint(current_sentence: str, next_sentence: str) -> bool:
    """Determine if this is a good place to break between chunks."""
    # Good breakpoints: end of paragraphs, after conclusions, before new topics
    current = current_sentence.strip().lower()
    next_sent = next_sentence.strip().lower()
    
    # End of paragraph indicators
    if current.endswith('.') and (not next_sent or next_sent[0].isupper()):
        return True
    
    # Conclusion indicators
    conclusion_words = ['therefore', 'thus', 'in conclusion', 'finally', 'as a result']
    if any(word in current for word in conclusion_words):
        return True
    
    # New topic indicators
    topic_starters = ['first', 'second', 'next', 'another', 'furthermore', 'moreover']
    if any(next_sent.startswith(word) for word in topic_starters):
        return True
    
    return False


def split_text_into_chunks(text: str, config: Dict[str, Any]) -> List[str]:
    """
    Split text into chunks at semantic boundaries (fallback method).
    
    Args:
        text: Document text
        config: Chunking configuration
        
    Returns:
        List of text chunks
    """
    chunks = []
    current_chunk = ""
    last_break_point = 0
    
    # Process text character by character
    for i in range(len(text)):
        current_chunk += text[i]
        
        # Check if we're at a potential break point
        is_break_point = text[i] in config["sentenceEndingChars"]
        
        if is_break_point:
            last_break_point = len(current_chunk)
        
        # If we've reached target chunk size and we have a break point, create a chunk
        if len(current_chunk) >= config["targetChunkSize"] and last_break_point > 0:
            # Create chunk up to the last break point
            chunk_text = current_chunk[:last_break_point]
            chunks.append(chunk_text)
            
            # Start new chunk with overlap
            overlap_start = max(0, last_break_point - config["overlapSize"])
            current_chunk = current_chunk[overlap_start:]
            last_break_point = 0
        
        # If we've reached max chunk size, force a break
        if len(current_chunk) >= config["maxChunkSize"]:
            chunks.append(current_chunk)
            current_chunk = ""
            last_break_point = 0
    
    # Add the final chunk if it's not empty and meets minimum size
    if len(current_chunk) >= config["minChunkSize"]:
        chunks.append(current_chunk)
    elif current_chunk and chunks:
        # Append to the last chunk if it's too small
        chunks[-1] += current_chunk
    elif current_chunk:
        # If it's the only chunk, keep it despite being small
        chunks.append(current_chunk)
    
    return chunks


def calculate_importance_score(
    heading: Dict[str, Any], text: str, chunk_index: int = 0
) -> float:
    """
    Calculate importance score for a chunk based on heading level and content.
    
    Args:
        heading: Section heading
        text: Chunk text
        chunk_index: Chunk index within section
        
    Returns:
        Importance score
    """
    score = 1.0
    
    # Higher score for higher-level headings (h1 > h2 > h3)
    if heading and heading.get("level"):
        score += (7 - min(heading["level"], 6)) * 0.1
    
    # Higher score for first chunk in a section
    if chunk_index == 0:
        score += 0.2
    
    # Higher score for chunks with keywords like "important", "key", "summary"
    keywords = ["important", "key", "summary", "conclusion", "result", "finding"]
    text_lower = text.lower()
    
    for keyword in keywords:
        if keyword in text_lower:
            score += 0.1
    
    # Analyze text density and information content
    # More sentences and fewer filler words indicate higher information density
    try:
        sentences = sent_tokenize(text)
        sentence_count = len(sentences)
        avg_sentence_length = len(text) / max(sentence_count, 1)
        
        # Reward moderate sentence length (not too short, not too long)
        if 10 <= avg_sentence_length <= 30:
            score += 0.1
        
        # Reward appropriate number of sentences
        if 3 <= sentence_count <= 10:
            score += 0.1
    except Exception:
        # If NLTK fails, don't adjust the score
        pass
    
    # Cap the score at 2.0
    return min(score, 2.0)
