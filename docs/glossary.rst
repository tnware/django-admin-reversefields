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

   Render Gate
      The first of three permission checkpoints. Runs during form ``__init__``
      (before templates render) to decide whether a :term:`virtual field <Virtual Field>` is
      visible, disabled, or hidden. By default it consults a base permission;
      enable ``reverse_render_uses_field_policy`` to use per-field
      :term:`policies <Policy>`. See :ref:`configuration-permissions`.

   Validation Gate
      The second permission checkpoint. Runs during form ``clean()`` once a
      selection exists. If a custom :term:`policy <Policy>` denies the selection,
      a field error is attached. See :ref:`configuration-permissions`.

   Persistence Gate
      The third and final permission checkpoint. Runs during form ``save()`` to
      filter the update payload so that unauthorized :term:`virtual fields <Virtual Field>`
      are excluded — even if a crafted POST included them. See
      :ref:`configuration-permissions`.

   Bulk Mode
      An optional per-field setting (``bulk=True`` on
      :class:`~django_admin_reversefields.mixins.ReverseRelationConfig`) that
      uses Django's ``.update()`` for :term:`binding <Binding>` and
      :term:`unbinding <Unbinding>` instead of individual model saves. Faster
      for large datasets but bypasses model signals (``pre_save``,
      ``post_save``). See :ref:`concepts-data-integrity`.
