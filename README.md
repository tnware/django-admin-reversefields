# django-admin-reversefields

[![PyPI - Downloads](https://img.shields.io/pypi/dw/django-admin-reversefields)](https://pypi.org/project/django-admin-reversefields/)
[![PyPI - Version](https://img.shields.io/pypi/v/django-admin-reversefields)](https://pypi.org/project/django-admin-reversefields/)

Manage reverse ForeignKey/OneToOne bindings directly from a parent model’s Django admin form using a small, declarative mixin.

- Add virtual fields to your `ModelAdmin` to bind/unbind reverse-side rows
- Keep selections in sync with transactional, unbind-before-bind updates
- Use stock admin widgets or plug in Unfold/DAL/custom widgets
- Optional, flexible permission gating with clear UX (hide/disable)

---

## Install

```bash
pip install django-admin-reversefields
```

Supported: Django 4.2/5.0/5.1/5.2; Python 3.10–3.13.

---

## Quickstart

```python
from django.contrib import admin
from django.db.models import Q

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)
from .models import Company, Department, Project


def unbound_or_current(qs, instance, request):
    if instance and instance.pk:
        return qs.filter(Q(company__isnull=True) | Q(company=instance))
    return qs.filter(company__isnull=True)


@admin.register(Company)
class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
    reverse_relations = {
        # Single-select: bind exactly one Department via its FK to Company
        "department_binding": ReverseRelationConfig(
            model=Department,
            fk_field="company",
            limit_choices_to=unbound_or_current,
        ),
        # Multi-select: manage the entire set of Projects pointing at the Company
        "assigned_projects": ReverseRelationConfig(
            model=Project,
            fk_field="company",
            multiple=True,
            # optional: ordering=("name",),
        ),
    }

    fieldsets = (("Relations", {"fields": ("department_binding", "assigned_projects")}),)
```

- Include each virtual field name (e.g. `"department_binding"`) in `fieldsets` or `fields` so the admin template renders it (or omit both `fields` and `fieldsets` and Django will render all fields, including the injected virtual fields).
- Limiters run per request/object; commonly: “unbound or currently bound”.

---

## Core concepts (tl;dr)

- Reverse fields are virtual `ModelChoiceField` / `ModelMultipleChoiceField` instances that point to the reverse-side model and its ForeignKey back to the admin’s model.
- Querysets and initial values are computed per request/object.
- On save, the mixin synchronizes the reverse-side ForeignKey(s) to match the submitted selection.
  - Single-select: sets the chosen row’s FK to the parent and unbinds any other rows pointing to it.
  - Multi-select: represents the entire desired set; rows not in the selection are unbound before binds.
- Transactions: by default `reverse_relations_atomic=True` wraps all updates in one `transaction.atomic()` block and applies unbinds before binds to minimize uniqueness conflicts.

Performance: enable `bulk=True` on a `ReverseRelationConfig` to use `.update()` for unbind/bind operations. This improves performance with large datasets but bypasses model signals. Use only if your app doesn’t depend on `pre_save`/`post_save` on the reverse model.

Important: for single-select, unbinding others requires the reverse FK to be `null=True`, or set `required=True` on the virtual field when it must never be empty; otherwise an unbind can raise `IntegrityError`.

---

## Permissions (optional)

Enable enforcement:

```python
class ServiceAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
    reverse_permissions_enabled = True
    reverse_permission_mode = "disable"  # or "hide"
```

- Precedence for allow/deny:
  1) Per-field `ReverseRelationConfig.permission`
  2) `reverse_permission_policy` (admin-wide)
  3) Default `user.has_perm("app.change_model")` on the reverse model
- Error message precedence: field override → per-field policy object → global policy object → default
- Disable vs hide:
  - "disable": render read-only and ignore posted changes. To avoid spurious validation, the mixin sets `required=False` on disabled reverse fields so forms won’t raise “This field is required.” when there is no initial value.
  - "hide": remove the field entirely.
- Optional: set `reverse_render_uses_field_policy=True` to have render-time visibility/disabled state decided by your per-field/global policy (called with `selection=None`).

Hidden/disabled fields are always ignored on save, so crafted POSTs cannot change unauthorized reverse fields.

---

## API surface

Import:

```python
from django_admin_reversefields.mixins import ReverseRelationAdminMixin, ReverseRelationConfig
```

`ReverseRelationConfig` (per virtual field):

- `model`: reverse-side `models.Model` that holds the ForeignKey to the admin model
- `fk_field`: name of that ForeignKey on `model`
- `label`, `help_text`: optional display strings
- `required`: enforce non-empty selection (default False)
- `multiple`: multi-select that syncs many rows (default False)
- `limit_choices_to`: callable `(qs, instance, request) -> qs` or `dict` passed to `.filter(**dict)`
- `widget`: widget instance or class; defaults to admin `Select`/`FilteredSelectMultiple`
- `ordering`: iterable for `.order_by()`
- `clean(instance, selection, request)`: optional domain validation; raise `forms.ValidationError` to block
- `permission`: optional policy (callable or object with `has_perm(...)`) to allow/deny edits
- `permission_denied_message`: message used when a denial becomes a field error
- `bulk`: when True, perform unbind/bind via `.update()` (bypasses model signals)

Mixin knobs:

- `reverse_relations`: mapping of virtual field name → config
- `reverse_relations_atomic`: wrap all updates in one transaction (default True)
- `reverse_permissions_enabled`: enforce permission checks (default False)
- `reverse_permission_mode`: "disable" | "hide"
- `reverse_permission_policy`: optional global policy
- `reverse_render_uses_field_policy`: use per-field/global policy at render time (selection=None)

---

## Recipes and docs

- [Quickstart](https://tnware.github.io/django-admin-reversefields/quickstart.html)
- [Core concepts](https://tnware.github.io/django-admin-reversefields/core-concepts.html)
- [Permissions](https://tnware.github.io/django-admin-reversefields/permissions-guide.html)
- [Architecture](https://tnware.github.io/django-admin-reversefields/architecture.html)
- [Recipes](https://tnware.github.io/django-admin-reversefields/recipes.html)
- [Caveats](https://tnware.github.io/django-admin-reversefields/caveats.html)
- [Rendering & Visibility](https://tnware.github.io/django-admin-reversefields/rendering.html)

---

## Development

We use [`uv`](https://github.com/astral-sh/uv) for tooling.

- `uv sync` — install project + docs deps
- `uv run ruff check .` — lint
- `uv run django-admin test` or `uv run python manage.py test` — tests
- `uv run sphinx-build -b html docs docs/_build/html -W` — docs build

Release:

```bash
uv build
Twine upload dist/*
```
