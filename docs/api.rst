API
===

.. autoclass:: django_admin_reversefields.mixins.ReverseRelationConfig
   :members:
   :show-inheritance:
   :no-index:

   .. attribute:: bulk
      :type: bool
      :value: False

      When ``True``, use Django's ``.update()`` method for bind/unbind operations 
      instead of individual model saves. This provides better performance for large 
      datasets but bypasses model signals (``pre_save``, ``post_save``, etc.).

      .. warning::
         
         Bulk operations bypass Django model signals. Only enable bulk mode when 
         your application doesn't rely on ``pre_save``, ``post_save``, or other 
         model signals for the reverse relationship model.

      **Default:** ``False`` (maintains backward compatibility)

      **Performance Trade-offs:**
      
      - **Advantages:** Reduced database round-trips, better performance with large datasets
      - **Disadvantages:** No model signal processing, less granular error handling

.. autoclass:: django_admin_reversefields.mixins.ReverseRelationAdminMixin
   :members:
   :show-inheritance:
   :no-index:

.. autoclass:: django_admin_reversefields.mixins.ReversePermissionPolicy
   :members:
   :no-index:
