"""
Tests for utility functions.
"""

import pytest
import sys
import tempfile
import json
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from utilities.helpers import (
    read_json, write_json, ensure_directory,
    flatten_list, chunk_list, Logger, timer
)


class TestJsonUtils:
    """Test JSON utility functions."""
    
    def test_write_and_read_json(self):
        """Test writing and reading JSON files."""
        test_data = {"test": "data", "number": 42, "list": [1, 2, 3]}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            write_json(test_data, temp_file)
            loaded_data = read_json(temp_file)
            assert loaded_data == test_data
        finally:
            os.unlink(temp_file)


class TestDirectoryUtils:
    """Test directory utility functions."""
    
    def test_ensure_directory(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = os.path.join(temp_dir, "test", "nested", "directory")
            result_path = ensure_directory(test_path)
            
            assert result_path.exists()
            assert result_path.is_dir()
            assert str(result_path) == test_path


class TestListUtils:
    """Test list utility functions."""
    
    def test_flatten_list(self):
        """Test list flattening."""
        nested = [[1, 2], [3, 4], [5]]
        flattened = flatten_list(nested)
        assert flattened == [1, 2, 3, 4, 5]
        
        # Test empty lists
        assert flatten_list([]) == []
        assert flatten_list([[], []]) == []
    
    def test_chunk_list(self):
        """Test list chunking."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        chunks = chunk_list(data, 3)
        expected = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        assert chunks == expected
        
        # Test with remainder
        chunks_with_remainder = chunk_list([1, 2, 3, 4, 5], 2)
        expected_remainder = [[1, 2], [3, 4], [5]]
        assert chunks_with_remainder == expected_remainder


class TestLogger:
    """Test Logger class."""
    
    def test_logger_creation(self):
        """Test logger instantiation."""
        logger = Logger("test")
        assert logger.name == "test"
        
        default_logger = Logger()
        assert default_logger.name == "playground"
    
    # Note: Testing actual log output would require capturing stdout
    # which is more complex, so we'll just test the basic functionality


class TestTimer:
    """Test timer decorator."""
    
    def test_timer_decorator(self):
        """Test that timer decorator works without breaking function."""
        @timer
        def dummy_function(x, y):
            return x + y
        
        result = dummy_function(2, 3)
        assert result == 5