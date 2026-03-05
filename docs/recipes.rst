Recipes
=======

.. contents:: Page contents
   :depth: 1
   :local:

.. _recipe-single-binding:

Single binding (Company ↔ Department)
-------------------------------------

.. code-block:: python

   from django.contrib import admin
   from django.db.models import Q
   from django_admin_reversefields.mixins import ReverseRelationAdminMixin, ReverseRelationConfig

   def unbound_or_current(queryset, instance, request):
       """Offer unassigned rows plus rows already bound to this company."""
       if instance and instance.pk:
           return queryset.filter(Q(company__isnull=True) | Q(company=instance))
       return queryset.filter(company__isnull=True)

   @admin.register(Company)
   class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_relations = {
           "department_binding": ReverseRelationConfig(
               model=Department,
               fk_field="company",
               limit_choices_to=unbound_or_current,
               help_text=(
                   "Choices are limited to departments that are unassigned or "
                   "already assigned to this company."
               ),
               # Add bulk=True for better performance with large datasets
               # bulk=True,  # Uncomment if you don't need model signals
           )
       }
       fieldsets = (("Departments", {"fields": ("department_binding",)}),)

.. note:: Rendering Rules

   - If you declare ``fieldsets`` or ``fields``, include the virtual name
     (e.g., ``"department_binding"``) so Django renders it.
   - If neither is declared, Django renders all form fields and the injected
     virtual fields appear automatically. The mixin appends the virtual names in
     ``get_fields`` and injects their form fields in ``get_form``.
   - If you override ``get_fields`` without calling ``super()``, or you return a
     custom ``fields`` list that omits the virtual names, the admin template
     will not render them (even though the form contains them).

.. _recipe-multiple-binding:

Multiple binding (Company ↔ Projects)
-------------------------------------

.. code-block:: python

   from django.db.models import Q


   def available_projects_queryset(queryset, instance, request):
       if instance and instance.pk:
           return queryset.filter(Q(company__isnull=True) | Q(company=instance))
       return queryset.filter(company__isnull=True)


   @admin.register(Company)
   class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_relations = {
           "assigned_projects": ReverseRelationConfig(
               model=Project,
               fk_field="company",
               multiple=True,
               ordering=("name",),
               limit_choices_to=available_projects_queryset,
               # Enable bulk operations for better performance with many projects
               # bulk=True,  # Uncomment if you don't need model signals
           )
       }
       fieldsets = (("Projects", {"fields": ("assigned_projects",)}),)
       # Rendering rules are the same as the single-binding recipe.
       # Ensure all updates occur as a single unit (default True)
       reverse_relations_atomic = True

.. _recipe-validation-hooks:

Validation hooks (business rules)
---------------------------------

Forbid unbinding unless a condition is met:

.. code-block:: python

   from django import forms

   def forbid_unbind(instance, selection, request):
       if selection is None:
           raise forms.ValidationError("Cannot unbind department right now")

   @admin.register(Company)
   class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_relations = {
           "department_binding": ReverseRelationConfig(
               model=Department,
               fk_field="company",
               multiple=False,
               clean=forbid_unbind,
           )
       }

.. _recipe-permissions:

Permissions on reverse fields
-----------------------------

.. dropdown:: Baseline change-policy setup
   :open:

   .. seealso::
      For a deep dive into the permission system, see the :doc:`configuration`.

   Require ``change`` permission on the reverse model, with disabled field mode:

   .. code-block:: python

      @admin.register(Company)
      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_permissions_enabled = True
          reverse_permission_mode = "disable"  # or "hide"
          reverse_relations = {
              "department_binding": ReverseRelationConfig(
                  model=Department,
                  fk_field="company",
                  multiple=False,
              )
          }
          # Optional: let per-field/global policies decide visibility at render time
          # (policy must handle selection=None)
          # reverse_render_uses_field_policy = True

.. dropdown:: Adapt legacy ``has_perm`` helpers

   .. code-block:: python

      class CanBindAdapter:
          permission_denied_message = "Not allowed to bind this item."
          def has_perm(self, request, obj, config, selection):
              # delegate to some legacy checker
              return legacy_can_bind(request.user, selection)

      @admin.register(Company)
      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_permissions_enabled = True
          reverse_relations = {
              "department_binding": ReverseRelationConfig(
                  model=Department,
                  fk_field="company",
                  multiple=False,
                  permission=CanBindAdapter(),
              )
          }

.. dropdown:: Customise :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.has_reverse_change_permission`

   .. code-block:: python

      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_permissions_enabled = True
          def has_reverse_change_permission(self, request, obj, config, selection=None):
              # Example: object-level check (works with backends that support object perms)
              app, model = config.model._meta.app_label, config.model._meta.model_name
              codename = f"{app}.change_{model}"
              if selection is None:
                  return request.user.has_perm(codename)
              if isinstance(selection, (list, tuple)):
                  return all(request.user.has_perm(codename, s) for s in selection)
              return request.user.has_perm(codename, selection)

.. dropdown:: Swap the permission codename

   .. code-block:: python

      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_permissions_enabled = True
          def has_reverse_change_permission(self, request, obj, config, selection=None):
              app, model = config.model._meta.app_label, config.model._meta.model_name
              return request.user.has_perm(f"{app}.add_{model}")  # require add instead of change

.. dropdown:: Callable per-field policy

   .. code-block:: python

      # Callable policy per field (signature must include config)
      def only_allow_special(request, obj, config, selection):
          return getattr(selection, "name", "") == "Special"

      @admin.register(Company)
      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_permissions_enabled = True
          reverse_relations = {
              "department_binding": ReverseRelationConfig(
                  model=Department,
                  fk_field="company",
                  multiple=False,
                  permission=only_allow_special,
                  # Optional field override for the message; otherwise the policy
                  # object's message (if any) or a default will be used.
                  permission_denied_message="You do not have permission to choose this value.",
              )
          }

.. dropdown:: Policy object (Protocol implementation)

   .. code-block:: python

      class StaffOnlyPolicy:
          permission_denied_message = "Staff access required"

          def __call__(self, request, obj, config, selection):
              return getattr(request.user, "is_staff", False)

      @admin.register(Company)
      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_permissions_enabled = True
          reverse_relations = {
              "department_binding": ReverseRelationConfig(
                  model=Department,
                  fk_field="company",
                  multiple=False,
                  permission=StaffOnlyPolicy(),
              )
          }

.. dropdown:: Global policy (admin-wide)

   .. code-block:: python

      def can_bind(request, obj, config, selection):
          # Example: require a custom permission codename on the reverse model
          app = config.model._meta.app_label
          model = config.model._meta.model_name
          return request.user.has_perm(f"{app}.can_bind_{model}")

      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_permissions_enabled = True
          reverse_permission_policy = staticmethod(can_bind)

   .. note::
     Using ``staticmethod`` prevents Python from binding ``self`` to the callable.
     The mixin expects a callable with the signature ``(request, obj, config, selection)``.

.. dropdown:: Alternative (instance assignment)

   .. code-block:: python

      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_permissions_enabled = True

          def get_form(self, request, obj=None, **kwargs):
              # Assign policy on the instance; no staticmethod needed
              self.reverse_permission_policy = can_bind
              return super().get_form(request, obj, **kwargs)

OneToOneField (Company ↔ CompanySettings)
-----------------------------------------

.. code-block:: python

   def only_unbound_or_current(qs, instance, request):
       if instance and instance.pk:
           return qs.filter(Q(company__isnull=True) | Q(company=instance))
       return qs.filter(company__isnull=True)

   @admin.register(Company)
   class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_relations = {
           "settings_binding": ReverseRelationConfig(
               model=CompanySettings,
               fk_field="company",
               multiple=False,
               required=True,
               limit_choices_to=only_unbound_or_current,
           )
       }
       fieldsets = (("Settings", {"fields": ("settings_binding",)}),)

Request-aware validation hook (use request.user)
------------------------------------------------

Sometimes validation must depend on the current user or other request context.
The ``clean`` hook receives the ``request`` so you can implement user-specific rules.

.. code-block:: python

   from django import forms
   from django.contrib import admin
   from django_admin_reversefields.mixins import ReverseRelationAdminMixin, ReverseRelationConfig

   def staff_only(instance, selection, request):
       if not getattr(request, "user", None) or not request.user.is_staff:
           raise forms.ValidationError("Not permitted")

   @admin.register(Company)
   class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_relations = {
           "department_binding": ReverseRelationConfig(
               model=Department,
               fk_field="company",
               multiple=False,
               required=False,
               clean=staff_only,  # gets (instance, selection, request)
           )
       }

If the user is not staff, the form will include a field error on ``department_binding``
with the message "Not permitted" and the update will be blocked.

.. _recipe-render-policy:

Render-time policy (control visibility/editability before selection)
--------------------------------------------------------------------

Enable ``reverse_render_uses_field_policy`` to let per-field or global policies
decide whether a virtual field is visible or editable at render time. This is
useful when you want to hide or disable a field based on ``request.user`` or
other context before any selection exists.

.. code-block:: python

   from django.contrib import admin
   from django_admin_reversefields.mixins import (
       ReverseRelationAdminMixin,
       ReverseRelationConfig,
   )

   # Hide binding from non-staff users at render time
   def staff_only_policy(request, obj, config, selection):
       return getattr(request.user, "is_staff", False)

   @admin.register(Company)
   class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_permissions_enabled = True
       reverse_permission_mode = "hide"  # or "disable"
       reverse_render_uses_field_policy = True
       reverse_relations = {
           "department_binding": ReverseRelationConfig(
               model=Department,
               fk_field="company",
               multiple=False,
               permission=staff_only_policy,
           )
       }

With ``hide`` mode, a field is removed entirely for non-staff users. Switch to
``disable`` to keep it visible but read-only. Policies are evaluated with
``selection=None`` during render.

.. _recipe-bulk-operations:

Bulk operations for performance optimization
--------------------------------------------

When managing large numbers of reverse relationships, enable bulk mode to use 
Django's ``.update()`` method instead of individual model saves. This provides 
significant performance improvements but bypasses model signals.

.. code-block:: python

   from django.contrib import admin
   from django.db.models import Q
   from django_admin_reversefields.mixins import ReverseRelationAdminMixin, ReverseRelationConfig

   def available_departments_queryset(queryset, instance, request):
       if instance and instance.pk:
           return queryset.filter(Q(company__isnull=True) | Q(company=instance))
       return queryset.filter(company__isnull=True)

   @admin.register(Company)
   class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_relations = {
           # Single-select with bulk operations
           "primary_department": ReverseRelationConfig(
               model=Department,
               fk_field="company",
               bulk=True,  # Use bulk operations for performance
               limit_choices_to=available_departments_queryset,
           ),
           # Multi-select with bulk operations - ideal for large datasets
           "all_projects": ReverseRelationConfig(
               model=Project,
               fk_field="company",
               multiple=True,
               bulk=True,  # Bulk operations for multiple selections
               ordering=("name",),
               limit_choices_to=available_departments_queryset,
           ),
           # Mixed configuration - some bulk, some individual
           "critical_departments": ReverseRelationConfig(
               model=Department,
               fk_field="company",
               multiple=True,
               bulk=False,  # Keep individual saves for signal processing
               ordering=("name",),
           )
       }
       fieldsets = (
           ("Department Assignments", {"fields": ("primary_department", "all_projects")}),
           ("Critical Departments", {"fields": ("critical_departments",)}),
       )

.. note:: **Performance Guidelines**

   - **Use bulk mode when:** Managing hundreds/thousands of objects, performance is critical, no signal dependencies
   - **Avoid bulk mode when:** Models rely on ``pre_save``/``post_save`` signals, need granular error handling
   - **Mixed approach:** Use bulk for high-volume fields, individual saves for signal-dependent fields

.. dropdown:: Performance comparison example

   .. code-block:: python

      # Example performance difference with 1000 Department objects:
      
      # Individual saves (bulk=False):
      # - 1000+ database queries (one per save)
      # - All model signals triggered
      # - ~2-5 seconds for large operations
      
      # Bulk operations (bulk=True):
      # - 2 database queries (one unbind, one bind)
      # - No model signals triggered  
      # - ~0.1-0.2 seconds for same operation
      
      # Use bulk mode for this scenario:
      reverse_relations = {
          "department_assignments": ReverseRelationConfig(
              model=Department,
              fk_field="company", 
              multiple=True,
              bulk=True,  # 10-50x performance improvement
              ordering=("name",),
          )
      }

.. warning::

   **Signal Bypass Warning:** Bulk operations use ``.update()`` which bypasses:
   
   - ``pre_save`` and ``post_save`` signals
   - Model ``save()`` method overrides
   - Custom validation in ``save()`` methods
   - Audit logging that depends on save signals
   
   Only enable bulk mode when these features aren't required for your reverse relationship model.

.. _recipe-ajax-widget:

Third-party widgets (AJAX search)
---------------------------------

.. dropdown:: End-to-end DAL integration
   :open:

   .. seealso::
      See :doc:`advanced` for more details on widget customisation.

   You can use any compatible third-party widget, which is especially useful for
   fields with many choices. The example below shows a conceptual integration with
   `django-autocomplete-light <https://django-autocomplete-light.readthedocs.io/>`_
   to provide an AJAX-powered search widget.

   .. tab-set::

      .. tab-item:: forms.py

         First, define an autocomplete view.

         .. code-block:: python

            # In forms.py or a dedicated file
            from dal import autocomplete
            from .models import Department

            class DepartmentAutocomplete(autocomplete.Select2QuerySetView):
                def get_queryset(self):
                    # Don't forget to filter out results based on user permissions
                    if not self.request.user.is_authenticated:
                        return Department.objects.none()

                    qs = Department.objects.all()

                    if self.q:
                        qs = qs.filter(name__icontains=self.q)

                    return qs

      .. tab-item:: urls.py

         Next, register the autocomplete view's URL.

         .. code-block:: python

            # In urls.py
            from .forms import DepartmentAutocomplete

            urlpatterns = [
                path(
                    "department-autocomplete/",
                    DepartmentAutocomplete.as_view(),
                    name="department-autocomplete",
                ),
            ]

      .. tab-item:: admin.py

         Finally, configure the reverse relation to use the widget.

         .. code-block:: python

            # In admin.py
            from dal import autocomplete

            @admin.register(Company)
            class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                reverse_relations = {
                    "department_binding": ReverseRelationConfig(
                        model=Department,
                        fk_field="company",
                        # The widget is instantiated with the URL of the autocomplete view
                        widget=autocomplete.ModelSelect2(url="department-autocomplete"),
                    )
                }
                fieldsets = (("Departments", {"fields": ("department_binding",)}),)

                class Media:
                    js = ("admin/js/jquery.init.js",)  # Ensure jQuery is loaded

   .. note::
      The admin must include the necessary form media for the widget to work.
      Ensure jQuery is loaded if your widget depends on it.
