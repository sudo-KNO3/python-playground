<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Python Playground - Copilot Instructions

This is a Python development playground repository designed for experimentation and learning.

## Project Structure

- `src/` - Main source code modules
- `experiments/` - Quick experiments and prototypes  
- `utilities/` - Reusable utility functions and helpers
- `tests/` - Test files using pytest
- `data/` - Sample data files
- `docs/` - Project documentation

## Development Guidelines

- Use Python 3.8+ with type hints
- Follow PEP 8 style guidelines
- Write tests for new functionality
- Use the utilities package for common operations
- Place experimental code in the experiments/ directory

## Available Tools

- pytest for testing
- black for code formatting  
- flake8 for linting
- mypy for type checking
- Pre-configured pyproject.toml with tool settings

## Quick Commands

- Run tests: `python -m pytest tests/ -v`
- Format code: `black .`
- Check types: `mypy .`
- Run sample experiment: `python experiments/fibonacci_experiment.py`