Rendering & Visibility
======================

This guide explains how the mixin gets your virtual fields onto the page, how to
control whether they show up, and when they are editable vs. read-only. It ties
the lifecycle together so you can reason about layout and permissions in one place.

.. contents:: Page contents
   :depth: 1
   :local:

How virtual fields appear
-------------------------

- ``get_fields``: The mixin appends the virtual names declared in
  :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_relations` to the
  list of fields returned by ``ModelAdmin.get_fields`` so templates know about them.
- ``get_form``: It strips those names from the base ``fields`` passed to the form factory
  (to avoid unknown-field errors), then injects real
  :class:`~django.forms.ModelChoiceField` /
  :class:`~django.forms.ModelMultipleChoiceField` instances with the configured
  label, help text, widget, queryset, and initial selection.

Layout rules (fields vs. fieldsets)
-----------------------------------

- If you declare ``fieldsets`` or ``fields``, you must include the virtual names
  there (e.g. ``"department_binding"``) or the admin template will not render
  them.
- If neither is declared, Django renders all form fields by default and the
  injected virtual fields appear automatically.
- If you override ``get_fields`` without calling ``super()``, or you return a
  hard-coded ``fields`` list that omits the virtual names, the form will still
  contain the injected fields but the template will not render them.

Visibility vs. editability
--------------------------

When :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_permissions_enabled`
is True the mixin runs a render gate for each virtual field:

- Mode is controlled by :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_permission_mode`:

  - ``"hide"`` removes the field from the form (no input is rendered).
  - ``"disable"`` keeps it visible but sets ``disabled=True`` and relaxes ``required`` to avoid
    spurious "This field is required." errors.
- By default, the render gate consults a base/global permission (roughly
  ``change_<reverse_model>``). To let per-field/global policies decide visibility
  up front, set
  :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_render_uses_field_policy`
  to True. In that mode
  :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.has_reverse_change_permission`
  is called with ``selection=None``.

Validation and persistence nuances
----------------------------------

- Validation errors for permission denials are attached only when a custom
  policy (per-field or global) participates. Base-only denials rely on the UI
  gating above.
- Hidden/disabled fields are ignored during save. The mixin filters the payload
  of reverse fields during ``save()`` so crafted POSTs cannot change a hidden or
  disabled field.

Troubleshooting
---------------

- Field does not render

  - Ensure its virtual name appears in ``fieldsets`` or ``fields`` (or do not declare either),
    and avoid overriding ``get_fields`` without calling ``super()``.

- Field renders but is read-only

  - Check ``reverse_permissions_enabled`` + ``reverse_permission_mode``, and whether
    ``reverse_render_uses_field_policy`` is True with a policy that denies access for the
    current user.

.. seealso::
   - :doc:`permissions-guide` — Modes (hide/disable), render-time policies, message
     precedence.
   - :doc:`querysets-and-widgets` — Limiting choices and customizing widgets.
   - :doc:`recipes` — End-to-end examples.
   - :doc:`core-concepts` — Lifecycle summary.
