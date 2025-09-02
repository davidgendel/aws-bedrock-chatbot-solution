"""
Tests for document_utils.py - Document processing utilities.
"""
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add backend path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from document_utils import (
    extract_headings, estimate_heading_level, get_text_from_block,
    get_value_block, process_table, extract_text_from_document
)


class TestDocumentUtils(unittest.TestCase):
    """Test document utilities functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.sample_markdown = """# Main Title
This is some content under the main title.

## Subtitle 1
Content under subtitle 1.

### Sub-subtitle
More content here.

## Subtitle 2
Final content."""
        
        self.sample_html = """<html>
<body>
<h1>Main Title</h1>
<p>This is some content under the main title.</p>
<h2>Subtitle 1</h2>
<p>Content under subtitle 1.</p>
<h3>Sub-subtitle</h3>
<p>More content here.</p>
<h2>Subtitle 2</h2>
<p>Final content.</p>
</body>
</html>"""
    
    def test_extract_headings_markdown(self):
        """Test extracting headings from markdown."""
        headings = extract_headings(self.sample_markdown, "md")
        
        self.assertEqual(len(headings), 4)
        self.assertEqual(headings[0]["level"], 1)
        self.assertEqual(headings[0]["text"], "Main Title")
        self.assertEqual(headings[1]["level"], 2)
        self.assertEqual(headings[1]["text"], "Subtitle 1")
        self.assertEqual(headings[2]["level"], 3)
        self.assertEqual(headings[2]["text"], "Sub-subtitle")
        self.assertEqual(headings[3]["level"], 2)
        self.assertEqual(headings[3]["text"], "Subtitle 2")
    
    def test_extract_headings_html(self):
        """Test extracting headings from HTML."""
        headings = extract_headings(self.sample_html, "html")
        
        self.assertEqual(len(headings), 4)
        self.assertEqual(headings[0]["level"], 1)
        self.assertEqual(headings[0]["text"], "Main Title")
        self.assertEqual(headings[1]["level"], 2)
        self.assertEqual(headings[1]["text"], "Subtitle 1")
    
    def test_extract_headings_unsupported_format(self):
        """Test extracting headings from unsupported format."""
        headings = extract_headings("Some text", "txt")
        self.assertEqual(len(headings), 0)
    
    def test_extract_headings_empty_content(self):
        """Test extracting headings from empty content."""
        headings = extract_headings("", "md")
        self.assertEqual(len(headings), 0)
    
    def test_estimate_heading_level_heading_type(self):
        """Test estimating heading level for HEADING type."""
        block = {"TextType": "HEADING"}
        level = estimate_heading_level(block)
        self.assertEqual(level, 1)
    
    def test_estimate_heading_level_colon_ending(self):
        """Test estimating heading level for text ending with colon."""
        block = {"Text": "Section Title:"}
        level = estimate_heading_level(block)
        self.assertEqual(level, 2)
    
    def test_estimate_heading_level_default(self):
        """Test estimating heading level default case."""
        block = {"Text": "Regular text"}
        level = estimate_heading_level(block)
        self.assertEqual(level, 3)
    
    def test_get_text_from_block_direct_text(self):
        """Test getting text from block with direct text."""
        block = {"Text": "Sample text"}
        text = get_text_from_block(block, [])
        self.assertEqual(text, "Sample text")
    
    def test_get_text_from_block_with_relationships(self):
        """Test getting text from block with child relationships."""
        all_blocks = [
            {"Id": "1", "Text": "Parent"},
            {"Id": "2", "Text": "Child1"},
            {"Id": "3", "Text": "Child2"}
        ]
        
        block = {
            "Id": "1",
            "Relationships": [
                {
                    "Type": "CHILD",
                    "Ids": ["2", "3"]
                }
            ]
        }
        
        text = get_text_from_block(block, all_blocks)
        self.assertIn("Child1", text)
        self.assertIn("Child2", text)
    
    def test_get_text_from_block_no_text(self):
        """Test getting text from block with no text."""
        block = {"Id": "1"}
        text = get_text_from_block(block, [])
        self.assertEqual(text, "")
    
    def test_get_value_block_success(self):
        """Test getting value block successfully."""
        all_blocks = [
            {"Id": "1", "Text": "Key"},
            {"Id": "2", "Text": "Value"}
        ]
        
        key_block = {
            "Id": "1",
            "Relationships": [
                {
                    "Type": "VALUE",
                    "Ids": ["2"]
                }
            ]
        }
        
        value_block = get_value_block(key_block, all_blocks)
        self.assertIsNotNone(value_block)
        self.assertEqual(value_block["Text"], "Value")
    
    def test_get_value_block_no_relationships(self):
        """Test getting value block with no relationships."""
        key_block = {"Id": "1"}
        value_block = get_value_block(key_block, [])
        self.assertIsNone(value_block)
    
    def test_get_value_block_no_value_relationship(self):
        """Test getting value block with no VALUE relationship."""
        key_block = {
            "Id": "1",
            "Relationships": [
                {
                    "Type": "CHILD",
                    "Ids": ["2"]
                }
            ]
        }
        value_block = get_value_block(key_block, [])
        self.assertIsNone(value_block)
    
    def test_process_table_basic(self):
        """Test processing basic table."""
        table_block = {
            "Id": "1",
            "BlockType": "TABLE",
            "Relationships": [
                {
                    "Type": "CHILD",
                    "Ids": ["2", "3", "4", "5"]
                }
            ]
        }
        
        all_blocks = [
            table_block,
            {
                "Id": "2", 
                "BlockType": "CELL", 
                "RowIndex": 1, 
                "ColumnIndex": 1, 
                "Text": "Cell1",
                "Relationships": [{"Type": "CHILD", "Ids": ["1"]}]
            },
            {
                "Id": "3", 
                "BlockType": "CELL", 
                "RowIndex": 1, 
                "ColumnIndex": 2, 
                "Text": "Cell2",
                "Relationships": [{"Type": "CHILD", "Ids": ["1"]}]
            },
            {
                "Id": "4", 
                "BlockType": "CELL", 
                "RowIndex": 2, 
                "ColumnIndex": 1, 
                "Text": "Cell3",
                "Relationships": [{"Type": "CHILD", "Ids": ["1"]}]
            },
            {
                "Id": "5", 
                "BlockType": "CELL", 
                "RowIndex": 2, 
                "ColumnIndex": 2, 
                "Text": "Cell4",
                "Relationships": [{"Type": "CHILD", "Ids": ["1"]}]
            }
        ]
        
        with patch('document_utils.get_text_from_block', side_effect=lambda b, _: b.get("Text", "")):
            table = process_table(table_block, all_blocks)
            
            self.assertEqual(len(table["rows"]), 2)
            self.assertEqual(len(table["rows"][0]), 2)
            self.assertEqual(table["rows"][0][0], "Cell1")
            self.assertEqual(table["rows"][0][1], "Cell2")
            self.assertEqual(table["rows"][1][0], "Cell3")
            self.assertEqual(table["rows"][1][1], "Cell4")
    
    @patch('boto3.client')
    def test_extract_text_from_document_text_file(self, mock_boto3_client):
        """Test extracting text from text file."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock S3 head_object response
        mock_s3_client.head_object.return_value = {
            'ContentLength': 1024,
            'LastModified': Mock(isoformat=Mock(return_value='2023-01-01T00:00:00')),
            'Metadata': {'author': 'Test Author'}
        }
        
        # Mock S3 get_object response
        text_content = "This is test content from a text file."
        mock_s3_client.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=text_content.encode()))
        }
        
        result = extract_text_from_document('test-bucket', 'test.txt')
        
        self.assertIn('text', result)
        self.assertEqual(result['text'], text_content)
        self.assertEqual(result['metadata']['fileName'], 'test.txt')
        self.assertEqual(result['metadata']['fileExtension'], 'txt')
        self.assertEqual(result['metadata']['fileSize'], 1024)
    
    @patch('boto3.client')
    def test_extract_text_from_document_pdf_with_textract(self, mock_boto3_client):
        """Test extracting text from PDF using Textract."""
        mock_s3_client = Mock()
        mock_textract_client = Mock()
        mock_boto3_client.side_effect = [mock_s3_client, mock_textract_client]
        
        # Mock S3 head_object response
        mock_s3_client.head_object.return_value = {
            'ContentLength': 2048,
            'LastModified': Mock(isoformat=Mock(return_value='2023-01-01T00:00:00')),
            'Metadata': {}
        }
        
        # Mock Textract response for analyze_document
        mock_textract_client.analyze_document.return_value = {
            'Blocks': [
                {'BlockType': 'PAGE'},
                {'BlockType': 'LINE', 'Text': 'First line of text'},
                {'BlockType': 'LINE', 'Text': 'Second line of text'},
                {'BlockType': 'WORD', 'Text': 'Word1'}
            ]
        }
        
        result = extract_text_from_document('test-bucket', 'test.pdf')
        
        self.assertIn('text', result)
        self.assertIn('First line of text', result['text'])
        self.assertIn('Second line of text', result['text'])
        self.assertEqual(result['metadata']['fileName'], 'test.pdf')
        self.assertEqual(result['metadata']['fileExtension'], 'pdf')
    
    @patch('boto3.client')
    def test_extract_text_from_document_large_file_error(self, mock_boto3_client):
        """Test extracting text from file that exceeds size limit."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock S3 head_object response with large file size
        mock_s3_client.head_object.return_value = {
            'ContentLength': 200 * 1024 * 1024,  # 200MB
            'LastModified': Mock(isoformat=Mock(return_value='2023-01-01T00:00:00')),
            'Metadata': {}
        }
        
        with self.assertRaises(ValueError) as context:
            extract_text_from_document('test-bucket', 'large-file.pdf')
        
        self.assertIn('exceeds limit', str(context.exception))
    
    @patch('boto3.client')
    def test_extract_text_from_document_unsupported_format(self, mock_boto3_client):
        """Test extracting text from unsupported file format."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock S3 head_object response
        mock_s3_client.head_object.return_value = {
            'ContentLength': 1024,
            'LastModified': Mock(isoformat=Mock(return_value='2023-01-01T00:00:00')),
            'Metadata': {}
        }
        
        with self.assertRaises(ValueError) as context:
            extract_text_from_document('test-bucket', 'test.xyz')
        
        self.assertIn('Unsupported file type', str(context.exception))
    
    @patch('boto3.client')
    def test_extract_text_from_document_s3_error(self, mock_boto3_client):
        """Test extracting text with S3 error."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        mock_s3_client.head_object.side_effect = Exception("S3 access denied")
        
        with self.assertRaises(Exception) as context:
            extract_text_from_document('test-bucket', 'test.txt')
        
        self.assertIn('S3 access denied', str(context.exception))
    
    @patch('boto3.client')
    def test_extract_text_from_document_json_format(self, mock_boto3_client):
        """Test extracting text from JSON file."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock S3 responses
        mock_s3_client.head_object.return_value = {
            'ContentLength': 512,
            'LastModified': Mock(isoformat=Mock(return_value='2023-01-01T00:00:00')),
            'Metadata': {}
        }
        
        json_content = {"title": "Test Document", "content": "This is JSON content"}
        mock_s3_client.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=json.dumps(json_content).encode()))
        }
        
        result = extract_text_from_document('test-bucket', 'test.json')
        
        self.assertIn('text', result)
        self.assertIn('Test Document', result['text'])
        self.assertIn('JSON content', result['text'])
        self.assertEqual(result['metadata']['fileExtension'], 'json')
    
    @patch('boto3.client')
    def test_extract_text_from_document_html_format(self, mock_boto3_client):
        """Test extracting text from HTML file."""
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock S3 responses
        mock_s3_client.head_object.return_value = {
            'ContentLength': 256,
            'LastModified': Mock(isoformat=Mock(return_value='2023-01-01T00:00:00')),
            'Metadata': {}
        }
        
        html_content = "<html><body><h1>HTML Title</h1><p>HTML content</p></body></html>"
        mock_s3_client.get_object.return_value = {
            'Body': Mock(read=Mock(return_value=html_content.encode()))
        }
        
        result = extract_text_from_document('test-bucket', 'test.html')
        
        self.assertIn('text', result)
        self.assertEqual(result['metadata']['fileExtension'], 'html')
    
    @patch('boto3.client')
    def test_extract_text_from_document_with_structure(self, mock_boto3_client):
        """Test extracting text with document structure."""
        mock_s3_client = Mock()
        mock_textract_client = Mock()
        mock_boto3_client.side_effect = [mock_s3_client, mock_textract_client]
        
        # Mock S3 responses
        mock_s3_client.head_object.return_value = {
            'ContentLength': 1024,
            'LastModified': Mock(isoformat=Mock(return_value='2023-01-01T00:00:00')),
            'Metadata': {}
        }
        
        # Mock Textract response with table
        mock_textract_client.analyze_document.return_value = {
            'Blocks': [
                {'BlockType': 'PAGE'},
                {'BlockType': 'LINE', 'Text': 'Document title'},
                {
                    'BlockType': 'TABLE',
                    'Id': 'table1',
                    'Relationships': [{'Type': 'CHILD', 'Ids': ['cell1', 'cell2']}]
                },
                {
                    'BlockType': 'CELL',
                    'Id': 'cell1',
                    'RowIndex': 1,
                    'ColumnIndex': 1,
                    'Text': 'Cell 1'
                },
                {
                    'BlockType': 'CELL',
                    'Id': 'cell2',
                    'RowIndex': 1,
                    'ColumnIndex': 2,
                    'Text': 'Cell 2'
                }
            ]
        }
        
        with patch('document_utils.process_table') as mock_process_table:
            mock_process_table.return_value = {'rows': [['Cell 1', 'Cell 2']]}
            
            result = extract_text_from_document('test-bucket', 'test.pdf')
            
            self.assertIn('text', result)
            self.assertIn('structure', result)
            self.assertIn('metadata', result)
            mock_process_table.assert_called_once()


if __name__ == '__main__':
    unittest.main()
