Querysets & widgets
===================

Learn how to control which objects appear in each :term:`virtual field <Virtual Field>` and how to tune
its presentation in the admin. Practical examples live in
:ref:`recipe-single-binding` and :ref:`recipe-multiple-binding`.

Scoping choices
---------------

``ReverseRelationConfig.limit_choices_to`` accepts either a ``dict`` (mirroring
Django's ``ModelAdmin`` behaviour) or a callable of the form
``(queryset, instance, request) -> queryset``. Callables let you combine
request-aware filtering with inclusion of already-related rows, ensuring users
can keep existing :term:`bindings <Binding>` even when a global filter would hide them.

Ordering selections
-------------------

Apply ``ReverseRelationConfig.ordering`` to control how the queryset is sorted
before rendering. The tuple mirrors Django's ``QuerySet.order_by`` parameters and
runs after ``limit_choices_to`` so you can safely rely on any additional filters
applied there.

Custom widgets
--------------

Every :term:`virtual field <Virtual Field>` can override the default widget via
``ReverseRelationConfig.widget``. Supply either a widget instance or a widget
class. This works for stock Django form widgets as well as third-party options
such as Unfold Select2 or Django Autocomplete Light.

.. seealso::
   :doc:`advanced` for a complete DAL example.
