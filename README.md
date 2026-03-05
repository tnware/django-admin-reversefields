# django-admin-reversefields

<p align="left">
  <a href="https://pypi.org/project/django-admin-reversefields/">
    <img alt="PyPI version" src="https://img.shields.io/pypi/v/django-admin-reversefields">
  </a>
  <a href="https://pypi.org/project/django-admin-reversefields/">
    <img alt="PyPI downloads" src="https://img.shields.io/pypi/dw/django-admin-reversefields">
  </a>
  <img alt="Python versions" src="https://img.shields.io/pypi/pyversions/django-admin-reversefields">
  <img alt="Django versions" src="https://img.shields.io/badge/Django-4.2%20%7C%205.0%20%7C%205.1%20%7C%205.2-0C4B33">
  <a href="https://tnware.github.io/django-admin-reversefields/">
    <img alt="Docs" src="https://img.shields.io/badge/docs-online-blue">
  </a>
</p>

Manage reverse `ForeignKey` / `OneToOne` relationships from the **parent** change form in Django admin.

`django-admin-reversefields` adds **parent-side selector fields** (single or multi-select) that stay in sync with the child rows on save — without hand-rolling custom forms, querysets, or save logic.

<p align="left">
  <a href="https://tnware.github.io/django-admin-reversefields/quickstart.html">Quickstart</a>
  ·
  <a href="https://tnware.github.io/django-admin-reversefields/recipes.html">Recipes</a>
  ·
  <a href="https://tnware.github.io/django-admin-reversefields/caveats.html">Caveats</a>
</p>

---

## Why

Django admin gives you **inlines** for reverse relations. They’re great for creating or editing related rows, but they don’t give you a simple selector to attach **existing** child objects to a parent from the parent form.

When you implement this yourself, you usually repeat the same plumbing:

- form field + widget wiring
- queryset filtering
- initial value population
- unbind / bind save logic
- transaction handling

This package turns that pattern into a reusable mixin + config.

---

## What it does

You have a parent model (Organization / Company / Tenant) and a child model (Site / Department / Project) where the child has a `ForeignKey` to the parent.

This package adds **virtual fields** to the parent admin form so you can select which existing child rows belong to the parent. On save, it synchronizes the child rows’ foreign keys to match the selection.

Supports:

- single-select or multi-select
- choice filtering (example: “unassigned or already assigned to this parent”)
- transactional synchronization on save

---

## Install

    pip install django-admin-reversefields

Supported versions:

- Django: 4.2, 5.0, 5.1, 5.2
- Python: 3.10–3.13

---

## Quickstart

Example: assign `Site` rows to an `Organization` from the `Organization` admin page.

```python
from django.contrib import admin
from django_admin_reversefields.mixins import ReverseRelationAdminMixin, ReverseRelationConfig

@admin.register(Organization)
class OrganizationAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
    reverse_relations = {
        "sites": ReverseRelationConfig(
            model=Site,
            fk_field="organization",
            multiple=True,
            limit_choices_to=unbound_or_current,  # optional
        ),
    }

    fieldsets = (
        ("Details", {"fields": ("name",)}),
        ("Sites", {"fields": ("sites",)}),
    )
```

Include each virtual field name in `fieldsets` (or `fields`). When you save the parent, the mixin updates the child rows’ foreign keys to match the current selection.

---

## Development

This project uses `uv` for local tooling.

Setup:

    uv sync

Common commands:

    uv run ruff check .
    uv run django-admin test
    uv run sphinx-build -b html docs docs/_build/html -W

Run the demo/test app:

    export DJANGO_DB_NAME=db.sqlite3
    uv run python manage.py migrate
    uv run python manage.py seed
    uv run python manage.py runserver

Log in at `/admin/` with `admin` / `admin` and edit a company to see the reverse fields.

---

## Release

    uv build
    twine upload dist/*

---

## License

See [LICENSE](LICENSE)
