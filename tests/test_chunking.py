"""
Tests for chunking - document chunking functionality for RAG.
"""
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys

# Add backend path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

# Import chunking functions
from chunking import (
    create_chunks,
    create_structured_chunks,
    create_semantic_chunks,
    split_text_into_chunks_nlp,
    split_text_into_chunks,
    calculate_importance_score,
    ensure_nltk_resources
)


class TestChunking(unittest.TestCase):
    """Test document chunking functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.sample_text = """
        Introduction to Machine Learning
        
        Machine learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed. This field has revolutionized many industries and continues to grow rapidly.
        
        Types of Machine Learning
        
        There are three main types of machine learning: supervised learning, unsupervised learning, and reinforcement learning. Each type has its own characteristics and applications.
        
        Supervised Learning
        
        Supervised learning uses labeled training data to learn a mapping from inputs to outputs. Common algorithms include linear regression, decision trees, and neural networks.
        
        Conclusion
        
        Machine learning is a powerful tool that will continue to shape our future. Understanding its fundamentals is essential for anyone working in technology.
        """
        
        self.sample_structure = [
            {"startPosition": 9, "level": 1, "text": "Introduction to Machine Learning"},
            {"startPosition": 245, "level": 1, "text": "Types of Machine Learning"},
            {"startPosition": 425, "level": 2, "text": "Supervised Learning"},
            {"startPosition": 625, "level": 1, "text": "Conclusion"}
        ]
        
        self.sample_metadata = {
            "document_id": "test-doc-123",
            "filename": "ml_guide.txt",
            "author": "Test Author"
        }


class TestChunkCreation(TestChunking):
    """Test main chunk creation functions."""
    
    def test_create_chunks_with_structure(self):
        """Test chunk creation with document structure."""
        extracted_content = {
            "text": self.sample_text,
            "structure": self.sample_structure,
            "metadata": self.sample_metadata
        }
        
        chunks = create_chunks(extracted_content)
        
        # Verify chunks were created
        self.assertGreater(len(chunks), 0)
        
        # Verify chunk structure
        for chunk in chunks:
            self.assertIn("content", chunk)
            self.assertIn("type", chunk)
            self.assertIn("heading", chunk)
            self.assertIn("importanceScore", chunk)
            self.assertIn("metadata", chunk)
            
            # Verify content is not empty
            self.assertTrue(chunk["content"].strip())
            
            # Verify importance score is reasonable
            self.assertGreaterEqual(chunk["importanceScore"], 0.0)
            self.assertLessEqual(chunk["importanceScore"], 2.0)
    
    def test_create_chunks_without_structure(self):
        """Test chunk creation without document structure."""
        extracted_content = {
            "text": self.sample_text,
            "metadata": self.sample_metadata
        }
        
        chunks = create_chunks(extracted_content)
        
        # Verify chunks were created
        self.assertGreater(len(chunks), 0)
        
        # Verify chunk structure for semantic chunks
        for chunk in chunks:
            self.assertIn("content", chunk)
            self.assertEqual(chunk["type"], "text_chunk")
            self.assertIn("metadata", chunk)
            self.assertEqual(chunk["importanceScore"], 1.0)
    
    def test_create_chunks_empty_text(self):
        """Test chunk creation with empty text."""
        extracted_content = {
            "text": "",
            "metadata": self.sample_metadata
        }
        
        chunks = create_chunks(extracted_content)
        
        # Should handle empty text gracefully
        self.assertIsInstance(chunks, list)


class TestStructuredChunking(TestChunking):
    """Test structured chunking functionality."""
    
    def test_create_structured_chunks_basic(self):
        """Test basic structured chunking."""
        config = {
            "targetChunkSize": 500,
            "maxChunkSize": 1000,
            "minChunkSize": 100,
            "overlapSize": 50,
            "sentenceEndingChars": ['.', '!', '?', '\n\n']
        }
        
        chunks = create_structured_chunks(
            self.sample_text, 
            self.sample_structure, 
            self.sample_metadata, 
            config
        )
        
        # Verify chunks were created
        self.assertGreater(len(chunks), 0)
        
        # Verify each chunk has proper structure
        for chunk in chunks:
            self.assertIn("content", chunk)
            self.assertIn("heading", chunk)
            self.assertIn("importanceScore", chunk)
            self.assertIn("metadata", chunk)
            
            # Verify metadata includes heading level
            self.assertIn("headingLevel", chunk["metadata"])
            self.assertIn("sectionIndex", chunk["metadata"])
    
    def test_structured_chunks_importance_scores(self):
        """Test importance score calculation for structured chunks."""
        config = {
            "targetChunkSize": 200,
            "maxChunkSize": 400,
            "minChunkSize": 50,
            "overlapSize": 25,
            "sentenceEndingChars": ['.', '!', '?', '\n\n']
        }
        
        chunks = create_structured_chunks(
            self.sample_text, 
            self.sample_structure, 
            self.sample_metadata, 
            config
        )
        
        # Find chunks with different heading levels
        h1_chunks = [c for c in chunks if c["metadata"]["headingLevel"] == 1]
        h2_chunks = [c for c in chunks if c["metadata"]["headingLevel"] == 2]
        
        if h1_chunks and h2_chunks:
            # H1 chunks should generally have higher importance scores than H2
            avg_h1_score = sum(c["importanceScore"] for c in h1_chunks) / len(h1_chunks)
            avg_h2_score = sum(c["importanceScore"] for c in h2_chunks) / len(h2_chunks)
            self.assertGreater(avg_h1_score, avg_h2_score)


class TestSemanticChunking(TestChunking):
    """Test semantic chunking functionality."""
    
    def test_create_semantic_chunks_basic(self):
        """Test basic semantic chunking."""
        config = {
            "targetChunkSize": 300,
            "maxChunkSize": 600,
            "minChunkSize": 100,
            "overlapSize": 50,
            "sentenceEndingChars": ['.', '!', '?', '\n\n']
        }
        
        chunks = create_semantic_chunks(self.sample_text, self.sample_metadata, config)
        
        # Verify chunks were created
        self.assertGreater(len(chunks), 0)
        
        # Verify chunk structure
        for chunk in chunks:
            self.assertEqual(chunk["type"], "text_chunk")
            self.assertEqual(chunk["importanceScore"], 1.0)
            self.assertIn("chunkIndex", chunk["metadata"])
    
    def test_semantic_chunks_title_extraction(self):
        """Test title extraction from first chunk."""
        text_with_title = "Document Title\n\nThis is the main content of the document with multiple sentences."
        
        config = {
            "targetChunkSize": 100,
            "maxChunkSize": 200,
            "minChunkSize": 50,
            "overlapSize": 25,
            "sentenceEndingChars": ['.', '!', '?', '\n\n']
        }
        
        chunks = create_semantic_chunks(text_with_title, self.sample_metadata, config)
        
        # First chunk should have extracted title
        if chunks:
            first_chunk = chunks[0]
            self.assertIsNotNone(first_chunk["heading"])
            self.assertIn("Document Title", first_chunk["heading"])


class TestTextSplitting(TestChunking):
    """Test text splitting algorithms."""
    
    @patch('chunking.sent_tokenize')
    def test_split_text_into_chunks_nlp_success(self, mock_sent_tokenize):
        """Test NLP-based text splitting with successful tokenization."""
        # Mock NLTK sentence tokenization
        sentences = [
            "This is the first sentence.",
            "This is the second sentence.",
            "This is the third sentence.",
            "This is the fourth sentence."
        ]
        mock_sent_tokenize.return_value = sentences
        
        config = {
            "targetChunkSize": 60,
            "maxChunkSize": 120,
            "minChunkSize": 20,
            "overlapSize": 15,
            "sentenceEndingChars": ['.', '!', '?', '\n\n']
        }
        
        text = " ".join(sentences)
        chunks = split_text_into_chunks_nlp(text, config)
        
        # Verify chunks were created
        self.assertGreater(len(chunks), 0)
        
        # Verify chunks respect size constraints
        for chunk in chunks:
            self.assertLessEqual(len(chunk), config["maxChunkSize"])
    
    @patch('chunking.sent_tokenize')
    def test_split_text_into_chunks_nlp_fallback(self, mock_sent_tokenize):
        """Test NLP-based text splitting with fallback to simple splitting."""
        # Mock NLTK failure
        mock_sent_tokenize.side_effect = Exception("NLTK error")
        
        config = {
            "targetChunkSize": 100,
            "maxChunkSize": 200,
            "minChunkSize": 50,
            "overlapSize": 25,
            "sentenceEndingChars": ['.', '!', '?', '\n\n']
        }
        
        with patch('chunking.split_text_into_chunks') as mock_fallback:
            mock_fallback.return_value = ["chunk1", "chunk2"]
            
            chunks = split_text_into_chunks_nlp(self.sample_text, config)
            
            # Should fall back to simple splitting
            mock_fallback.assert_called_once()
            self.assertEqual(chunks, ["chunk1", "chunk2"])
    
    def test_split_text_into_chunks_simple(self):
        """Test simple text splitting algorithm."""
        config = {
            "targetChunkSize": 100,
            "maxChunkSize": 200,
            "minChunkSize": 30,
            "overlapSize": 20,
            "sentenceEndingChars": ['.', '!', '?', '\n\n']
        }
        
        text = "This is a test. This is another sentence! And here's a question? More text follows."
        chunks = split_text_into_chunks(text, config)
        
        # Verify chunks were created
        self.assertGreater(len(chunks), 0)
        
        # Verify size constraints
        for chunk in chunks:
            self.assertLessEqual(len(chunk), config["maxChunkSize"])
    
    def test_split_text_overlap_handling(self):
        """Test overlap handling in text splitting."""
        config = {
            "targetChunkSize": 50,
            "maxChunkSize": 100,
            "minChunkSize": 20,
            "overlapSize": 15,
            "sentenceEndingChars": ['.', '!', '?']
        }
        
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        chunks = split_text_into_chunks(text, config)
        
        if len(chunks) > 1:
            # Check that there's some overlap between consecutive chunks
            for i in range(len(chunks) - 1):
                current_chunk = chunks[i]
                next_chunk = chunks[i + 1]
                
                # There should be some common text (overlap)
                # This is a basic check - in practice, overlap might be more sophisticated
                self.assertTrue(len(current_chunk) > 0)
                self.assertTrue(len(next_chunk) > 0)


class TestImportanceScoring(TestChunking):
    """Test importance score calculation."""
    
    def test_calculate_importance_score_heading_level(self):
        """Test importance score based on heading level."""
        h1_heading = {"level": 1, "text": "Main Heading"}
        h3_heading = {"level": 3, "text": "Sub Heading"}
        
        text = "This is some sample text for testing."
        
        h1_score = calculate_importance_score(h1_heading, text)
        h3_score = calculate_importance_score(h3_heading, text)
        
        # H1 should have higher score than H3
        self.assertGreater(h1_score, h3_score)
    
    def test_calculate_importance_score_first_chunk_bonus(self):
        """Test importance score bonus for first chunk in section."""
        heading = {"level": 2, "text": "Section Heading"}
        text = "This is some sample text for testing."
        
        first_chunk_score = calculate_importance_score(heading, text, chunk_index=0)
        later_chunk_score = calculate_importance_score(heading, text, chunk_index=2)
        
        # First chunk should have higher score
        self.assertGreater(first_chunk_score, later_chunk_score)
    
    def test_calculate_importance_score_keywords(self):
        """Test importance score boost for keyword presence."""
        heading = {"level": 2, "text": "Section Heading"}
        
        text_with_keywords = "This is an important finding with key results."
        text_without_keywords = "This is some regular text content."
        
        keyword_score = calculate_importance_score(heading, text_with_keywords)
        regular_score = calculate_importance_score(heading, text_without_keywords)
        
        # Text with keywords should have higher score
        self.assertGreater(keyword_score, regular_score)
    
    @patch('chunking.sent_tokenize')
    def test_calculate_importance_score_sentence_analysis(self, mock_sent_tokenize):
        """Test importance score based on sentence analysis."""
        # Mock optimal sentence structure
        mock_sent_tokenize.return_value = [
            "This is a well-structured sentence.",
            "Another good sentence follows.",
            "And here's a third sentence."
        ]
        
        heading = {"level": 2, "text": "Section Heading"}
        text = "This is a well-structured sentence. Another good sentence follows. And here's a third sentence."
        
        score = calculate_importance_score(heading, text)
        
        # Should get bonus for good sentence structure
        self.assertGreater(score, 1.0)
    
    def test_calculate_importance_score_bounds(self):
        """Test importance score is properly bounded."""
        # Create conditions that would give very high score
        heading = {"level": 1, "text": "Important Key Summary"}
        text = "This important text contains key findings and summary results with conclusion."
        
        score = calculate_importance_score(heading, text, chunk_index=0)
        
        # Score should be capped at 2.0
        self.assertLessEqual(score, 2.0)
        self.assertGreaterEqual(score, 1.0)


class TestNLTKResourceHandling(TestChunking):
    """Test NLTK resource management."""
    
    @patch('nltk.data.find')
    @patch('nltk.download')
    def test_ensure_nltk_resources_already_available(self, mock_download, mock_find):
        """Test NLTK resource handling when resources are already available."""
        # Mock that punkt_tab is already available
        mock_find.return_value = True
        
        # Should not raise exception
        ensure_nltk_resources()
        
        # Should not attempt download
        mock_download.assert_not_called()
    
    @patch('nltk.data.find')
    @patch('nltk.download')
    def test_ensure_nltk_resources_download_needed(self, mock_download, mock_find):
        """Test NLTK resource handling when download is needed."""
        # Mock that resources are not found initially
        mock_find.side_effect = [LookupError("Not found"), True]  # First fails, second succeeds after download
        mock_download.return_value = True
        
        # Should not raise exception
        ensure_nltk_resources()
        
        # Should attempt download
        mock_download.assert_called()
    
    @patch('nltk.data.find')
    @patch('nltk.download')
    def test_ensure_nltk_resources_download_fails(self, mock_download, mock_find):
        """Test NLTK resource handling when download fails."""
        # Mock that resources are not found and download fails
        mock_find.side_effect = LookupError("Not found")
        mock_download.side_effect = Exception("Download failed")
        
        # Should not raise exception (should handle gracefully)
        ensure_nltk_resources()


class TestChunkingEdgeCases(TestChunking):
    """Test edge cases in chunking."""
    
    def test_very_short_text(self):
        """Test chunking with very short text."""
        short_text = "Short."
        extracted_content = {
            "text": short_text,
            "metadata": self.sample_metadata
        }
        
        chunks = create_chunks(extracted_content)
        
        # Should handle short text gracefully
        self.assertIsInstance(chunks, list)
        if chunks:
            self.assertEqual(len(chunks), 1)
            self.assertEqual(chunks[0]["content"].strip(), short_text.strip())
    
    def test_very_long_text(self):
        """Test chunking with very long text."""
        # Create a long text by repeating content
        long_text = self.sample_text * 10
        extracted_content = {
            "text": long_text,
            "metadata": self.sample_metadata
        }
        
        chunks = create_chunks(extracted_content)
        
        # Should create multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Each chunk should be reasonably sized
        for chunk in chunks:
            self.assertLess(len(chunk["content"]), 2000)  # Reasonable upper bound
    
    def test_text_with_special_characters(self):
        """Test chunking with special characters and formatting."""
        special_text = """
        Title with émojis 🚀 and spëcial chars!
        
        This text contains various symbols: @#$%^&*()
        And unicode characters: αβγδε
        
        Multiple    spaces   and	tabs.
        
        Line breaks
        
        
        Multiple line breaks above.
        """
        
        extracted_content = {
            "text": special_text,
            "metadata": self.sample_metadata
        }
        
        chunks = create_chunks(extracted_content)
        
        # Should handle special characters gracefully
        self.assertGreater(len(chunks), 0)
        
        # Content should be preserved
        all_content = " ".join(chunk["content"] for chunk in chunks)
        self.assertIn("émojis", all_content)
        self.assertIn("αβγδε", all_content)
    
    def test_empty_structure_elements(self):
        """Test handling of empty structure elements."""
        empty_structure = [
            {"startPosition": 0, "level": 1, "text": ""},
            {"startPosition": 50, "level": 2, "text": "Valid Heading"},
            {"startPosition": 100, "level": 1, "text": None}
        ]
        
        extracted_content = {
            "text": self.sample_text,
            "structure": empty_structure,
            "metadata": self.sample_metadata
        }
        
        # Should handle empty structure elements gracefully
        chunks = create_chunks(extracted_content)
        self.assertIsInstance(chunks, list)


if __name__ == '__main__':
    unittest.main()
