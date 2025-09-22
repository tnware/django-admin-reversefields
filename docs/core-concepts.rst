Core Concepts
=============

This chapter introduces the :term:`virtual fields <Virtual Field>` that
:class:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin` adds to a
:class:`~django.contrib.admin.ModelAdmin` and how the mixin keeps single and
multi-select :term:`bindings <Binding>` in sync. For complete admin examples, see
:ref:`recipe-single-binding` and :ref:`recipe-multiple-binding`.

.. contents:: Page contents
   :depth: 1
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

.. seealso::
   For visibility/editability at render time and layout rules, see :doc:`rendering`.

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

Permissions interaction
-----------------------

When permission enforcement is enabled and a reverse field is rendered in
``disable`` mode, the field becomes read-only and its POSTed value (if any) is
ignored. To avoid spurious validation errors, the mixin also forces
``required=False`` on such disabled fields — this prevents Django from raising
"This field is required." when there is no initial value and the browser omits
the disabled input from the submission.

.. seealso::
   - :doc:`architecture` dives deeper into how the mixin hooks into the admin form
     lifecycle.
   - :doc:`data-integrity` explains the transaction model that keeps :term:`bindings <Binding>`
     consistent across fields.
