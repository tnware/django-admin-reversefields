Concepts & Architecture
=======================

This chapter covers how
:class:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin` works:
the :term:`virtual fields <Virtual Field>` it injects, how the admin form
lifecycle is extended, how :term:`bindings <Binding>` are synchronised, and
what transaction guarantees apply. For complete admin examples, see
:ref:`recipe-single-binding` and :ref:`recipe-multiple-binding`.

.. contents:: Page contents
   :depth: 2
   :local:

What the mixin injects
----------------------

:class:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin` introduces *virtual* form fields that proxy the
reverse side of ForeignKey and OneToOne relationships. Those fields are declared
in :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_relations`.
If your admin declares ``fieldsets`` or ``fields``, you must include the virtual
names there so the Django template renders them. If your admin declares neither
``fieldsets`` nor ``fields``, Django renders all form fields by default and the
injected :term:`virtual fields <Virtual Field>` will appear automatically. This
works because the mixin's :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.get_fields`
appends the virtual names for you and :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.get_form`
injects the corresponding form fields dynamically.

.. note::

   If you override :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.get_fields`
   without calling ``super()``, or you hard-code ``fields``/``fieldsets`` and
   omit the virtual names, the admin template will not render the virtual
   fields. The form still contains them (the mixin injects them), but the layout
   derives from ``get_fields``/``fieldsets``.

During :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.get_form`
the mixin removes those virtual names from the base form
(avoiding "unknown field" errors), creates
:class:`~django.forms.ModelChoiceField`/:class:`~django.forms.ModelMultipleChoiceField`
instances on the fly, and wires up any labels, help texts, or widgets defined on
:class:`~django_admin_reversefields.mixins.ReverseRelationConfig`.

Request-aware querysets
-----------------------

Every :term:`virtual field <Virtual Field>` resolves its queryset and initial selection for the current
request. :attr:`~django_admin_reversefields.mixins.ReverseRelationConfig.limit_choices_to` can be a callable that
receives ``(queryset, instance, request)`` and returns a scoped queryset. This
lets you present only the objects a user is allowed to bind while still showing
items already attached to the instance under edit.

Single vs. multiple selections
------------------------------

:attr:`~django_admin_reversefields.mixins.ReverseRelationConfig.multiple` determines whether the field captures a
single object or a synchronised set:

* ``multiple=False`` (default) — behaves like a dropdown. The chosen object's
  ForeignKey is set to the admin object, and any other rows pointing at it are
  unbound.
* ``multiple=True`` — represents the *entire* desired set. After form submission
  the mixin unbinds rows not in the selection before :term:`binding <Binding>` the chosen ones to
  the instance. The resulting database state matches the submitted list exactly.

.. warning::
   Single-select unbinds all other objects pointing at the instance. Ensure the
   reverse ForeignKey is ``null=True``. If the relation must never be empty,
   set ``required=True`` on the :term:`virtual field <Virtual Field>` to prevent :term:`unbinding <Unbinding>` from raising
   an ``IntegrityError``.

Bulk operations and performance
-------------------------------

:class:`~django_admin_reversefields.mixins.ReverseRelationConfig` supports an optional ``bulk`` parameter
that changes how bind/unbind operations are performed:

* ``bulk=False`` (default) — uses individual model saves, triggering all Django
  model signals (``pre_save``, ``post_save``, etc.) for each affected object.
* ``bulk=True`` — uses Django's ``.update()`` method for better performance but
  bypasses model signals entirely.

**Performance considerations:**

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Aspect
     - Individual Saves (``bulk=False``)
     - Bulk Operations (``bulk=True``)
   * - Database round-trips
     - One per object
     - One per operation type
   * - Model signals
     - ✅ Triggered normally
     - ❌ Bypassed entirely
   * - Performance
     - Slower with large datasets
     - ✅ Significantly faster
   * - Error granularity
     - ✅ Per-object errors
     - Batch-level errors only
   * - Memory usage
     - Higher (object instantiation)
     - ✅ Lower (queryset operations)

**Best practices for bulk mode:**

* Enable bulk mode when managing hundreds or thousands of relationships
* Ensure your application doesn't depend on model signals for the reverse model
* Use bulk mode consistently across related configurations for optimal performance
* Consider the trade-off between performance and signal-based functionality

.. warning::

   Bulk operations bypass Django's model signal system. If your application relies
   on ``pre_save``, ``post_save``, ``pre_delete``, or other model signals for the
   reverse relationship model, do not enable bulk mode.

.. _concepts-form-lifecycle:

Form lifecycle
--------------

``ReverseRelationAdminMixin`` layers reverse-relation behaviour onto Django's
``ModelAdmin`` lifecycle. Configuration happens declaratively on the admin
class; the mixin then wires dynamic form fields, validation, permissions, and
persistence logic around Django's normal flow.

1. **Field declaration** — the admin declares :term:`virtual field <Virtual Field>` names in
   ``reverse_relations`` and lists them in ``fieldsets`` so the Django admin
   template renders them.
2. **Form construction** — :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.get_form`
   strips the virtual names out of the base ``fields`` argument (to avoid
   Django's "unknown field" errors) and delegates to ``super()``. After the base
   form class is produced, the mixin injects ``ModelChoiceField`` or
   ``ModelMultipleChoiceField`` instances for each configured relation. Querysets
   come from ``ReverseRelationConfig.limit_choices_to`` (callable or ``dict``)
   plus optional ``ordering``.
3. **Initial data** — the derived form's ``__init__`` resolves the queryset and
   current selections for the object under edit. :term:`Virtual fields <Virtual Field>` point at the
   reverse model's objects whose ForeignKey already references the parent
   instance.
4. **Render gate** — if ``reverse_permissions_enabled`` is true, the form checks
   permissions before rendering. By default this uses a base permission check,
   but can be configured to use the full permission :term:`policy <Policy>` to allow
   per-field visibility. Fields become hidden or disabled based on
   ``reverse_permission_mode``. See :ref:`configuration-visibility` for details.

Validation and permissions
--------------------------

* ``ReverseRelationConfig.clean`` hooks run during form ``clean()`` with
  ``(instance, selection, request)``. Use this for business rules such as
  capacity limits or forbidding unbinds.
* Permission evaluation happens twice:

  1. During ``clean()`` — when a custom :term:`policy <Policy>` (per-field or global) denies a
     specific selection, the field receives a validation error. Error messages
     resolve using the precedence described in :ref:`configuration-permissions`.
  2. During ``save()`` — unauthorized fields are excluded from the persistence
     payload to guard against crafted POSTs.

.. _concepts-persistence:

Persistence
-----------

``ModelForm.save`` delegates to the base implementation and then synchronizes
reverse relations via
:meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin._apply_reverse_relations`.
For each configured field:

* Multi-select fields compute the exact set of rows that should point at the
  parent instance. Items removed from the selection are unbound (ForeignKey set
  to ``None``) before new :term:`bindings <Binding>` are applied.
* Single-select fields unbind all rows except the chosen object, then bind the
  target if it is not already pointing at the instance.

When ``reverse_relations_atomic`` is ``True`` (the default) all configured
fields are synchronized inside a single transaction so either all :term:`bindings <Binding>` are
updated or none are. Unbinds happen before binds within each field to minimise
transient uniqueness conflicts on ``OneToOneField`` or ``unique`` ForeignKeys.

.. note:: ``commit=False``

   If a form is saved with ``commit=False``, the mixin defers reverse updates
   until :meth:`~django.contrib.admin.options.ModelAdmin.save_model`. The
   payload of authorized reverse fields is stored on the form instance and
   applied during the admin save hook.

.. _concepts-data-integrity:

Data integrity & transactions
-----------------------------

.. note::
   By default, the mixin wraps the entire update in a single
   :func:`django.db.transaction.atomic` block (``reverse_relations_atomic=True``).
   If any virtual field raises an error, the whole operation rolls back. You can
   opt out with ``reverse_relations_atomic=False`` if you prefer to persist
   changes field-by-field.

**Unbind before bind:**

Within each field's update, the mixin unbinds rows before :term:`binding <Binding>` new ones.
This avoids transient uniqueness errors on ``OneToOneField`` or ForeignKeys
with ``unique=True``, as the old relation is cleared before the new one is
claimed.

**One-to-one specifics:**

* Treat ``OneToOneField`` relations as single-select fields (``multiple=False``).
* If the reverse relation is non-nullable, you must configure ``required=True``
  or make the underlying database field nullable. Otherwise, :term:`unbinding <Unbinding>` an object
  would raise an ``IntegrityError``.

Extensibility checklist
-----------------------

* Provide custom widgets by supplying ``ReverseRelationConfig.widget`` with a
  widget instance or class (e.g., DAL/Unfold).
* Scope querysets dynamically with a callable ``limit_choices_to``. Callables
  receive the current request and instance, allowing per-user filtering.
* Implement per-field ``permission`` :term:`policies <Policy>` or assign
  ``reverse_permission_policy`` on the admin for global rules. :term:`Policies <Policy>` may be
  callables or objects implementing ``has_perm``.
* Override :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.has_reverse_change_permission`
  if you need to enforce different permission codenames (``add``/``delete``) or
  object-level checks.

.. seealso::
   - :doc:`configuration` — Permissions, visibility, querysets, and widgets.
   - :doc:`recipes` — End-to-end admin setups.
   - :doc:`caveats` — Operational edge-cases.
