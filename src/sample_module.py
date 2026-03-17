"""
Sample module demonstrating basic Python functionality.
This is a starting point for your experiments.
"""

from typing import List, Union


class Calculator:
    """A simple calculator for demonstration purposes."""

    @staticmethod
    def add(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Add two numbers."""
        return a + b

    @staticmethod
    def multiply(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Multiply two numbers."""
        return a * b

    @staticmethod
    def factorial(n: int) -> int:
        """Calculate factorial of a number."""
        if n < 0:
            raise ValueError("Factorial is not defined for negative numbers")
        if n == 0 or n == 1:
            return 1
        return n * Calculator.factorial(n - 1)


def greet(name: str, enthusiastic: bool = False) -> str:
    """Generate a greeting message."""
    greeting = f"Hello, {name}!"
    if enthusiastic:
        greeting += " Welcome to the Python playground!"
    return greeting


def process_numbers(numbers: List[Union[int, float]]) -> dict:
    """Process a list of numbers and return statistics."""
    if not numbers:
        return {"count": 0, "sum": 0, "average": 0, "min": None, "max": None}
    
    return {
        "count": len(numbers),
        "sum": sum(numbers),
        "average": sum(numbers) / len(numbers),
        "min": min(numbers),
        "max": max(numbers)
    }


if __name__ == "__main__":
    # Example usage
    calc = Calculator()
    print(greet("Python Developer", enthusiastic=True))
    print(f"2 + 3 = {calc.add(2, 3)}")
    print(f"5! = {calc.factorial(5)}")
    
    numbers = [1, 2, 3, 4, 5]
    stats = process_numbers(numbers)
    print(f"Statistics for {numbers}: {stats}")