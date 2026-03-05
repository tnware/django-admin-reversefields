Glossary
========

.. glossary::

   Virtual Field
      A form field dynamically injected into a :class:`~django.contrib.admin.ModelAdmin`
      by :class:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin`. It does
      not exist on the model itself but is used to manage the reverse relationship.
      See :doc:`concepts` for a walkthrough of how these form controls are
      created and synchronised.

   Binding
      The action of associating a reverse object with the current admin object by
      setting the :class:`~django.db.models.ForeignKey` on the reverse object to
      point to the current one. The transaction ordering is covered in
      :doc:`concepts`.

   Unbinding
      The action of disassociating a reverse object from the current admin object,
      typically by setting its ForeignKey to ``NULL``. Review the safeguards in
      :doc:`caveats` when unbinding non-nullable relations.

   Limiter
      A callable or dictionary provided in
      :class:`~django_admin_reversefields.mixins.ReverseRelationConfig` that filters the
      queryset for a virtual field, controlling which objects are available for
      selection. See :doc:`configuration` for implementation strategies.

   Policy
      A callable or object that implements permission checks for a virtual field. It
      determines whether a user has the authority to view, edit, or make specific
      selections. The evaluation flow is detailed in :doc:`configuration`.
