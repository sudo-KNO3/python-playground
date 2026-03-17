"""
Quick experiment: Data manipulation and visualization
A simple example showing how to work with data in the playground.
"""

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from utilities import Logger, timer
from src.sample_module import Calculator, process_numbers


@timer
def fibonacci_sequence(n: int) -> list:
    """Generate fibonacci sequence up to n terms."""
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    sequence = [0, 1]
    for i in range(2, n):
        sequence.append(sequence[i-1] + sequence[i-2])
    return sequence


def main():
    """Run the experiment."""
    logger = Logger("fibonacci-experiment")
    logger.info("Starting Fibonacci experiment")
    
    # Generate fibonacci numbers
    fib_numbers = fibonacci_sequence(15)
    logger.info(f"Generated {len(fib_numbers)} Fibonacci numbers")
    
    # Process the numbers
    stats = process_numbers(fib_numbers)
    logger.info(f"Statistics: {stats}")
    
    # Use calculator for some operations
    calc = Calculator()
    total = sum(fib_numbers)
    average = calc.add(0, stats['average'])  # Silly but demonstrates usage
    
    print(f"\nFibonacci sequence (15 terms): {fib_numbers}")
    print(f"Sum: {total}")
    print(f"Average: {average:.2f}")
    
    logger.info("Experiment completed successfully!")


if __name__ == "__main__":
    main()