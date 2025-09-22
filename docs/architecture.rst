Architecture
============

.. contents:: Page contents
   :depth: 1
   :local:

High-level components
---------------------

``ReverseRelationAdminMixin`` layers reverse-relation behaviour onto Django’s
``ModelAdmin`` lifecycle. Configuration happens declaratively on the admin
class; the mixin then wires dynamic form fields, validation, permissions, and
persistence logic around Django’s normal flow.

* ``reverse_relations`` — declarative mapping of :term:`virtual field <Virtual Field>` name to
  :class:`~django_admin_reversefields.mixins.ReverseRelationConfig`. Each
  configuration knows which reverse model to touch, which ForeignKey points
  back to the admin object, whether the selection is multi-valued, and how to
  scope the queryset.
* ``ReverseRelationConfig`` — per-field knobs for labels, widgets, queryset
  :term:`limiters <Limiter>`, validation hooks, and permission :term:`policies <Policy>`.
* ``reverse_relations_atomic`` — governs whether all reverse updates execute in
  a single :func:`django.db.transaction.atomic` block.
* Permission hooks — optional policies that gate rendering and persistence.

Form lifecycle
--------------

1. **Field declaration** — the admin declares :term:`virtual field <Virtual Field>` names in
   ``reverse_relations`` and lists them in ``fieldsets`` so the Django admin
   template renders them.
2. **Form construction** — :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.get_form`
   strips the virtual names out of the base ``fields`` argument (to avoid
   Django’s "unknown field" errors) and delegates to ``super()``. After the base
   form class is produced, the mixin injects ``ModelChoiceField`` or
   ``ModelMultipleChoiceField`` instances for each configured relation. Querysets
   come from ``ReverseRelationConfig.limit_choices_to`` (callable or ``dict``)
   plus optional ``ordering``.
3. **Initial data** — the derived form’s ``__init__`` resolves the queryset and
   current selections for the object under edit. :term:`Virtual fields <Virtual Field>` point at the
   reverse model’s objects whose ForeignKey already references the parent
   instance.
4. **Render gate** — if ``reverse_permissions_enabled`` is true, the form checks
   permissions before rendering. By default this uses a base permission check,
   but can be configured to use the full permission :term:`policy <Policy>` to allow
   per-field visibility. Fields become hidden or disabled based on
   ``reverse_permission_mode``.

.. seealso::
   The rendering flow and configuration options are detailed in :doc:`rendering`.

Validation and permissions
--------------------------

* ``ReverseRelationConfig.clean`` hooks run during form ``clean()`` with
  ``(instance, selection, request)``. Use this for business rules such as
  capacity limits or forbidding unbinds.
* Permission evaluation happens twice:

  1. During ``clean()`` — when a custom :term:`policy <Policy>` (per-field or global) denies a
     specific selection, the field receives a validation error. Error messages
     resolve using the precedence described in :doc:`permissions-guide`.
  2. During ``save()`` — unauthorized fields are excluded from the persistence
     payload to guard against crafted POSTs.

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
