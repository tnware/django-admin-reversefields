Quickstart
==========

Get up and running with
:class:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin` in just a
few steps. The snippets below are pulled directly from the accompanying test
project so they always reflect a working configuration.

.. contents:: Page contents
   :depth: 1
   :local:

.. seealso::

   Explore :doc:`core-concepts` for the lifecycle of the injected
   :term:`virtual fields <Virtual Field>` and dive into :doc:`recipes` for
   end-to-end examples, including permissions and validation hooks.


Install the package
-------------------

.. tab-set::

   .. tab-item:: pip

      .. code-block:: bash

         python -m pip install django-admin-reversefields

   .. tab-item:: uv

      .. code-block:: bash

         uv pip install django-admin-reversefields

.. note::

   The docs extras (``sphinx`` extensions) are listed in
   ``docs/requirements.txt``. Install them alongside the package when you plan
   to build the documentation locally.


Wire up your admin
------------------

Import the mixin and declare a mapping of :term:`virtual field <Virtual Field>`
names to :class:`~django_admin_reversefields.mixins.ReverseRelationConfig`
objects. Each configuration describes which reverse-side model and
``ForeignKey`` should be controlled from the parent admin.

.. literalinclude:: ../tests/admin.py
   :language: python
   :lines: 1-8
   :caption: Required imports in ``admin.py``

Register your :class:`~django.contrib.admin.ModelAdmin` by inheriting from the
mixin and declaring at least one reverse relation:

.. literalinclude:: ../tests/admin.py
   :language: python
   :lines: 10-28
   :caption: Minimal admin exposing two reverse bindings
   :emphasize-lines: 4-16

1. ``reverse_relations`` is a ``dict`` keyed by virtual field name.
2. Each :class:`~django_admin_reversefields.mixins.ReverseRelationConfig`
   declares the reverse model, the ``ForeignKey`` that points back, and any
   optional UI behaviour (labels, widgets, ordering).
3. Include the virtual field names inside ``fieldsets`` (or ``fields``) so
   Django renders them on the form. When neither is declared, Django will render
   all fields automatically.

.. warning::

   If the underlying reverse ``ForeignKey`` is ``null=False`` you must set
   ``required=True`` on the virtual field to avoid
   :class:`django.db.IntegrityError` when a user attempts to unbind the
   relation. See :doc:`caveats` for details.


Limit choices per request
-------------------------

The mixin resolves querysets on demand, so your limiter can be request-aware and
object-aware while still including items that are already bound to the current
instance.

.. code-block:: python

   from django.db.models import Q

   def unbound_or_current(queryset, instance, request):
       if instance and instance.pk:
           return queryset.filter(Q(service__isnull=True) | Q(service=instance))
       return queryset.filter(service__isnull=True)

   class ServiceAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_relations = {
           "site_binding": ReverseRelationConfig(
               model=Site,
               fk_field="service",
               limit_choices_to=unbound_or_current,
           )
       }

.. dropdown:: Configuration highlights

   - ``limit_choices_to`` accepts either a callable ``(queryset, instance,
     request) -> queryset`` or a ``dict`` that is passed to
     :meth:`~django.db.models.query.QuerySet.filter`.
   - ``multiple=True`` switches a field to a
     :class:`~django.forms.ModelMultipleChoiceField` and synchronises the entire
     set on save.
   - ``widget`` can be any Django form widget (including AJAX options such as
     Django Autocomplete Light). See :doc:`advanced` for an end-to-end
     walkthrough.
   - ``bulk=True`` enables bulk operations using ``.update()`` for better performance
     with large datasets, but bypasses model signals.


Enable bulk operations for performance
--------------------------------------

For large datasets where model signals aren't required, enable bulk mode to use 
Django's ``.update()`` method instead of individual saves:

.. code-block:: python

   class ServiceAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_relations = {
           # Single-select with bulk operations
           "site_binding": ReverseRelationConfig(
               model=Site,
               fk_field="service",
               bulk=True,  # Use .update() for better performance
               limit_choices_to=unbound_or_current,
           ),
           # Multi-select with bulk operations
           "assigned_extensions": ReverseRelationConfig(
               model=Extension,
               fk_field="service",
               multiple=True,
               bulk=True,  # Bulk operations for multiple selections
               ordering=("number",),
           )
       }

.. warning::

   **When to use bulk mode:**
   
   - ✅ Large datasets (hundreds/thousands of objects)
   - ✅ Performance is critical
   - ✅ No dependency on model signals (``pre_save``, ``post_save``, etc.)
   
   **When NOT to use bulk mode:**
   
   - ❌ Your models rely on ``pre_save`` or ``post_save`` signals
   - ❌ You need granular error handling per object
   - ❌ Small datasets where performance isn't a concern

What happens on save?
---------------------

.. dropdown:: Form lifecycle

   #. During :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.get_form`
      the mixin injects the virtual fields and computes their querysets.
   #. The generated form sets initial selections based on currently bound
      objects.
   #. When ``reverse_permissions_enabled`` is true, permission policies run at
      render, validation, and persistence time to guard the field.
   #. On ``form.save()``, the mixin applies transactional updates—unbind first,
      then bind—to keep the database consistent. When ``bulk=True``, operations
      use ``.update()`` for better performance. For details, see
      :doc:`data-integrity`.


Next steps
----------

.. rubric:: Build on the basics

- Follow the :ref:`recipe-single-binding` and
  :ref:`recipe-multiple-binding` walkthroughs for complete admin setups.
- Enforce permissions with :doc:`permissions-guide` and
  :ref:`recipe-permissions`.
- Consult the :doc:`api` reference when you need to override lifecycle methods
  such as :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.has_reverse_change_permission`.
