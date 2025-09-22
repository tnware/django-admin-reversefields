Querysets & Widgets
===================

.. contents:: Page contents
   :depth: 1
   :local:

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

.. caution:: Static dict vs callable

   A static ``dict`` filter cannot “reach back” to include objects already bound
   to the current instance unless they also match the dict. If you need the
   common pattern “unbound or currently bound”, prefer a callable, for example::

      from django.db.models import Q

      def unbound_or_current(qs, instance, request):
          if instance and instance.pk:
              return qs.filter(Q(company__isnull=True) | Q(company=instance))
          return qs.filter(company__isnull=True)

Empty querysets
---------------

When the limiter produces an empty queryset, the field renders with no choices.
Form submissions with an empty selection remain valid unless you set
``required=True`` on the :class:`~django_admin_reversefields.mixins.ReverseRelationConfig`.

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
   - :doc:`advanced` — Complete DAL/unfold widget examples.
   - :doc:`recipes` — End-to-end admin setups using limiters and widgets.
   - :doc:`rendering` — How fields appear and are included in the form.
