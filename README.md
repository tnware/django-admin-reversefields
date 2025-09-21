# django-admin-reversefields

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

Supported: Django 4.2/5.0/5.1; Python 3.10–3.13.

---

## Quickstart

```python
from django.contrib import admin
from django.db.models import Q

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)


def only_unbound_or_current(qs, instance, request):
    if instance and instance.pk:
        return qs.filter(Q(service__isnull=True) | Q(service=instance))
    return qs.filter(service__isnull=True)


@admin.register(Service)
class ServiceAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
    reverse_relations = {
        "site_binding": ReverseRelationConfig(
            model=Site,
            fk_field="service",
            limit_choices_to=only_unbound_or_current,
        )
    }

    fieldsets = (("Binding", {"fields": ("site_binding",)}),)
```

- Include the virtual field name (e.g. `"site_binding"`) in `fieldsets` so Django renders it.
- Limiters run per request/object; use them to include unbound items plus the current binding.

---

## Core concepts (tl;dr)

- Reverse fields are virtual `ModelChoiceField` / `ModelMultipleChoiceField` instances that point to the reverse-side model and its ForeignKey back to the admin’s model.
- Querysets and initial values are computed per request/object.
- On save, the mixin synchronizes the reverse-side ForeignKey(s) to match the submitted selection.
  - Single-select: sets the chosen row’s FK to the parent and unbinds any other rows pointing to it.
  - Multi-select: represents the entire desired set; rows not in the selection are unbound before binds.
- Transactions: by default `reverse_relations_atomic=True` wraps all updates in one `transaction.atomic()` block and applies unbinds before binds to minimize uniqueness conflicts.

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
- [Concepts](https://tnware.github.io/django-admin-reversefields/concepts.html)
- [Permissions](https://tnware.github.io/django-admin-reversefields/permissions-guide.html)
- [Architecture](https://tnware.github.io/django-admin-reversefields/architecture.html)
- [Recipes](https://tnware.github.io/django-admin-reversefields/recipes.html)
- [Caveats](https://tnware.github.io/django-admin-reversefields/caveats.html)

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
