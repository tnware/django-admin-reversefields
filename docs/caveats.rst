Caveats
=======

This page highlights operational edge-cases and limitations that are easy to
overlook while following the happy-path guides (:doc:`quickstart`,
:doc:`recipes`). Use it alongside :doc:`concepts` and
:doc:`configuration` when planning production roll-outs.

.. contents:: Page contents
   :local:
   :depth: 1

ForeignKey requirements
-----------------------

.. important::

   Ensure the reverse :class:`~django.db.models.ForeignKey` is nullable whenever
   :term:`unbinding <Unbinding>` should be allowed. If the column is
   ``null=False``, set ``required=True`` on the
   :class:`~django_admin_reversefields.mixins.ReverseRelationConfig` so the form
   blocks unbind attempts rather than raising
   :class:`django.db.IntegrityError`.

.. seealso::

   The persistence order (unbind before bind) is documented in
   :doc:`concepts`.

Transactional behaviour
-----------------------

.. note::

   :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_relations_atomic`
   defaults to ``True`` so every configured :term:`binding <Binding>` update runs
   inside a single :func:`django.db.transaction.atomic` block. Opt-out only when
   partial failures are acceptable. Even with atomic updates, concurrent edits on
   the same reverse object can still surface database-level uniqueness errors; be
   prepared to catch them in custom workflows.

Feature scope
-------------

.. admonition:: Supported relationship types
   :class: seealso

   The mixin targets reverse ``ForeignKey`` and ``OneToOneField`` bindings. It
   does **not** manage ``ManyToManyField`` relations or polymorphic relations
   such as :class:`~django.contrib.contenttypes.fields.GenericForeignKey`.

Display customisation
---------------------

The default widgets mirror the Django admin look-and-feel. Override
``ReverseRelationConfig.widget`` to plug in custom widgets (e.g. Unfold, DAL) or
see the :doc:`advanced` gallery for end-to-end examples. For request-aware
choice limiting, revisit :doc:`configuration`.

For how fields are included in the form and when they are visible vs. disabled,
see :doc:`configuration`.

Permission interplay
--------------------

.. caution::

   When ``reverse_permissions_enabled=True`` the mixin requires the user to pass
   one of the configured :term:`policies <Policy>` before persisting changes.
   Denied fields are ignored during save (including hidden/disabled fields), so
   crafted POSTs cannot sidestep the check. The render-time behaviour is controlled by
   :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_permission_mode`
   (``"disable"`` or ``"hide"``). Refer back to :doc:`configuration` for the
   evaluation flow and error-message precedence.

   By default, the render gate consults only a base/global permission. To let
   per-field/global policies influence visibility/editability, set
   ``reverse_render_uses_field_policy=True`` on the admin.

   See :doc:`configuration` for the end-to-end visibility and editability flow.

One-to-one specifics
--------------------

* Treat ``OneToOneField`` relations as single-select fields (``multiple=False``).
* If the reverse column is ``null=False``, enforce ``required=True`` on the
  :term:`virtual field <Virtual Field>` or make the column nullable.
* On admin "add" views, limiter callables cannot reference the object being
  created (because no primary key exists yet). The binding will be applied on the
  first successful save.

Performance at scale
--------------------

.. warning::

   For parents with very large child sets (tens of thousands of rows), plan for
   the following:

   * **Initial selection** — the mixin loads all currently bound primary keys to
     seed the form. Multi-select fields can therefore materialise large lists in
     memory.
   * **Limiter execution** — ``limit_choices_to`` runs on every form render.
     Optimise it with database filtering (``.filter()``, ``.exclude()``) and
     avoid iterating in Python. Consider `DAL <https://django-autocomplete-light.readthedocs.io/>`_
     style widgets to reduce the number of loaded options.
   * **Widget rendering** — if your widget surfaces related-object metadata,
     combine :meth:`~django.db.models.query.QuerySet.select_related` or
     :meth:`~django.db.models.query.QuerySet.prefetch_related` inside the limiter
     to control query counts.
