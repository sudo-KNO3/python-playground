"""
Tests for the sample module functionality.
"""

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.sample_module import Calculator, greet, process_numbers


class TestCalculator:
    """Test cases for Calculator class."""
    
    def test_add(self):
        """Test addition functionality."""
        assert Calculator.add(2, 3) == 5
        assert Calculator.add(-1, 1) == 0
        assert Calculator.add(0.5, 0.3) == pytest.approx(0.8)
    
    def test_multiply(self):
        """Test multiplication functionality."""
        assert Calculator.multiply(2, 3) == 6
        assert Calculator.multiply(-2, 3) == -6
        assert Calculator.multiply(0, 100) == 0
        assert Calculator.multiply(0.5, 2) == 1.0
    
    def test_factorial(self):
        """Test factorial calculation."""
        assert Calculator.factorial(0) == 1
        assert Calculator.factorial(1) == 1
        assert Calculator.factorial(5) == 120
        assert Calculator.factorial(3) == 6
    
    def test_factorial_negative(self):
        """Test factorial with negative input."""
        with pytest.raises(ValueError, match="Factorial is not defined for negative numbers"):
            Calculator.factorial(-1)


class TestGreet:
    """Test cases for greet function."""
    
    def test_simple_greeting(self):
        """Test basic greeting."""
        assert greet("Alice") == "Hello, Alice!"
        
    def test_enthusiastic_greeting(self):
        """Test enthusiastic greeting."""
        result = greet("Bob", enthusiastic=True)
        assert "Hello, Bob!" in result
        assert "Welcome to the Python playground!" in result


class TestProcessNumbers:
    """Test cases for process_numbers function."""
    
    def test_empty_list(self):
        """Test with empty list."""
        result = process_numbers([])
        expected = {"count": 0, "sum": 0, "average": 0, "min": None, "max": None}
        assert result == expected
    
    def test_single_number(self):
        """Test with single number."""
        result = process_numbers([5])
        expected = {"count": 1, "sum": 5, "average": 5.0, "min": 5, "max": 5}
        assert result == expected
    
    def test_multiple_numbers(self):
        """Test with multiple numbers."""
        result = process_numbers([1, 2, 3, 4, 5])
        expected = {"count": 5, "sum": 15, "average": 3.0, "min": 1, "max": 5}
        assert result == expected
    
    def test_negative_numbers(self):
        """Test with negative numbers."""
        result = process_numbers([-2, -1, 0, 1, 2])
        expected = {"count": 5, "sum": 0, "average": 0.0, "min": -2, "max": 2}
        assert result == expected