# AGENTS.md - AI Agent Guide for django-admin-reversefields

## Project Overview

**django-admin-reversefields** is a Django package that provides a mixin for managing reverse ForeignKey relationships directly from Django admin forms.

- **Package**: `django-admin-reversefields`
- **Python**: 3.10-3.13
- **Django**: 4.2, 5.0, 5.1, 5.2
- **Repository**: <https://github.com/tnware/django-admin-reversefields>
- **Documentation**: <https://tnware.github.io/django-admin-reversefields>

## Commands

### Development Setup

```bash
uv sync                    # Install dependencies
uv run ruff check .        # Lint code
uv run ruff format .       # Format code
```

### Testing

```bash
uv run django-admin test   # Run tests
uv run python manage.py test  # Alternative test command
```

### Documentation

```bash
uv run sphinx-build -b html docs docs/_build/html -W  # Build docs
```

### Building

```bash
uv build                  # Build package
```

## Code Style

- **Linter**: Ruff
- **Line length**: 100 characters
- **Target Python**: 3.11+
- **Docstrings**: Google style for Python files

## Working Guidelines

### File Structure

- `django_admin_reversefields/mixins.py` - Core implementation
- `tests/` - Test models, admin config, and test suite
- `docs/` - Sphinx documentation

### Key Classes

- `ReverseRelationAdminMixin` - Main mixin class
- `ReverseRelationConfig` - Configuration dataclass
- `ReversePermissionPolicy` - Permission protocol

### Testing Requirements

- All changes must pass existing tests
- Add tests for new functionality
- Test both single-select and multi-select scenarios
- Test permission modes (hide/disable)
- Test transaction rollback behavior

### Code Changes

- Follow existing patterns in `mixins.py`
- Maintain backward compatibility
- Update docstrings for new public methods
- Ensure proper error handling and validation
- Use type hints consistently

### Docs

- Update relevant `.rst` files in `docs/` for API changes
- Keep examples in sync with test code
- Maintain cross-references between documentation sections
