Data integrity & transactions
=============================

This guide explains how reverse :term:`bindings <Binding>` are persisted, what the default
transaction guarantees look like, and how to treat reverse ``OneToOneField``
relationships safely. For reference implementations, check
:ref:`recipe-single-binding` and :ref:`recipe-multiple-binding`.

Transactional saves
-------------------

.. note::
   By default, the mixin wraps the entire update in a single
   :func:`django.db.transaction.atomic` block (``reverse_relations_atomic=True``).
   If any virtual field raises an error, the whole operation rolls back. You can
   opt out with ``reverse_relations_atomic=False`` if you prefer to persist
   changes field-by-field.

Unbind before bind
------------------

.. note::
   Within each field's update, the mixin unbinds rows before :term:`binding <Binding>` new ones.
   This avoids transient uniqueness errors on ``OneToOneField`` or ForeignKeys
   with ``unique=True``, as the old relation is cleared before the new one is
   claimed.

One-to-one specifics
--------------------

.. note::
   Treat ``OneToOneField`` relations as single-select fields (``multiple=False``).
   If the reverse relation is non-nullable, you must configure ``required=True``
   or make the underlying database field nullable. Otherwise, :term:`unbinding <Unbinding>` an object
   would raise an ``IntegrityError``.
