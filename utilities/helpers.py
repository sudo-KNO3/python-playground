"""
Common utility functions for the playground.
"""

import json
import time
from typing import Any, Dict, List
from functools import wraps
from pathlib import Path


def timer(func):
    """Decorator to measure execution time of functions."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} took {end_time - start_time:.4f} seconds")
        return result
    return wrapper


def read_json(filepath: str) -> Dict[str, Any]:
    """Read JSON data from a file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def write_json(data: Dict[str, Any], filepath: str, indent: int = 2) -> None:
    """Write data to a JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=indent)


def ensure_directory(path: str) -> Path:
    """Create directory if it doesn't exist and return Path object."""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def flatten_list(nested_list: List[List[Any]]) -> List[Any]:
    """Flatten a nested list."""
    return [item for sublist in nested_list for item in sublist]


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


class Logger:
    """Simple logger for experiments."""
    
    def __init__(self, name: str = "playground"):
        self.name = name
        
    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message with timestamp."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] [{self.name}] {message}")
        
    def info(self, message: str) -> None:
        """Log an info message."""
        self.log(message, "INFO")
        
    def error(self, message: str) -> None:
        """Log an error message."""
        self.log(message, "ERROR")
        
    def debug(self, message: str) -> None:
        """Log a debug message."""
        self.log(message, "DEBUG")