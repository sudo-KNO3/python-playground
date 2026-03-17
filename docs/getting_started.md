# Python Playground Documentation

Welcome to the Python playground documentation! This is your workspace for experimenting with Python code.

## Project Structure

### src/
Main source code directory. Place your main modules and packages here.
- `sample_module.py` - Example module with Calculator class and utility functions

### experiments/
Directory for quick experiments and prototypes. Perfect for testing ideas before implementing them properly.
- `fibonacci_experiment.py` - Example experiment showing data processing

### utilities/
Reusable utility functions and helpers.
- `helpers.py` - Common utility functions, decorators, and classes

### tests/
Test files using pytest framework.
- `test_sample_module.py` - Tests for the sample module
- `test_utilities.py` - Tests for utility functions

### data/
Sample data files for experiments.
- `sample_data.json` - Example JSON data

## Getting Started

1. Set up your virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. Run tests to make sure everything works:
   ```bash
   pytest
   ```

4. Try running an experiment:
   ```bash
   python experiments/fibonacci_experiment.py
   ```

## Development Workflow

- Use `experiments/` for quick tests and ideas
- Move stable code to `src/` or `utilities/`
- Write tests for important functionality
- Use the pre-configured tools for code quality

## Available Tools

- **pytest**: Testing framework
- **black**: Code formatter
- **flake8**: Linter
- **mypy**: Type checker
- **isort**: Import sorter

Run formatting and linting:
```bash
black .
isort .
flake8 .
mypy .
```

## Tips

- Import utilities with: `from utilities import Logger, timer`
- Use the timer decorator to measure function performance
- The Logger class helps with debugging experiments
- Check `pyproject.toml` for tool configurations