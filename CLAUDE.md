# CLAUDE.md - Coding Guidelines

## Build/Test/Lint Commands
- Run app: `python app.py`
- Run tests: `pytest tests/`
- Run specific test: `pytest tests/test_file.py::test_function_name`
- Code formatting: `black .`
- Linting: `flake8 .`
- Type checking: `mypy .`
- Test with coverage: `pytest --cov=app tests/`

## Code Style Guidelines
- Use snake_case for files, variables, functions
- Use descriptive names with auxiliary verbs (is_active, has_permission)
- Include type hints in function signatures
- Follow functional programming paradigm; avoid classes except for Flask views
- Error handling: use early returns and guard clauses
- Blueprint organization for routes
- Standard imports order: stdlib, third-party, local
- Use docstrings for complex functions
- Security: validate all inputs, protect routes with decorators
- Testing: pytest fixtures, mocks for external dependencies
- Flask: use application factory pattern
- Proper error logging and user-friendly messages