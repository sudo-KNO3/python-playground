# Python Playground Repository

A development sandbox for experimenting with Python code, featuring organized structure for projects, utilities, and learning.

## Structure

```
├── src/           # Main source code
├── experiments/   # Quick experiments and prototypes
├── utilities/     # Reusable utility functions
├── tests/         # Test files
├── data/          # Sample data files
└── docs/          # Documentation
```

## Getting Started

1. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. Start coding in any directory that suits your needs!

## Features

- Pre-configured development environment
- Testing framework (pytest)
- Code formatting (black)
- Linting (flake8)
- Type checking (mypy)
- Organized project structure

## Usage

- Use `experiments/` for quick tests and prototypes
- Place reusable code in `utilities/`
- Write proper modules in `src/`
- Add tests in `tests/`