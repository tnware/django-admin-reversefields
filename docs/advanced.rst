Advanced
========

Advanced configuration examples and third-party widget integrations.

.. contents:: Page contents
   :depth: 1
   :local:

.. seealso::
   The :ref:`recipe-ajax-widget` provides a complete, end-to-end recipe for
   integrating third-party AJAX widgets.

Widgets
-------

-  **Default single-select**: ``forms.Select``
-  **Default multi-select**: ``forms.FilteredSelectMultiple``
-  **Custom**: Any Django form widget, including those from third-party apps
   like `django-autocomplete-light <https://django-autocomplete-light.readthedocs.io/>`_,
   can be provided via ``ReverseRelationConfig.widget``.

.. dropdown:: Example: django-autocomplete-light

   Provide a custom widget via ``ReverseRelationConfig.widget`` for large datasets.

   .. code-block:: python

      from django.contrib import admin
      from dal import autocomplete
      from django.db.models import Q
      from myapp.models import Company, Department

      from django_admin_reversefields.mixins import ReverseRelationAdminMixin, ReverseRelationConfig


      def company_department_queryset(queryset, instance, request):
          """Allow binding to departments that are unbound or already tied to ``instance``."""
          if instance and instance.pk:
              return queryset.filter(Q(company__isnull=True) | Q(company=instance))
          return queryset.filter(company__isnull=True)


      class DepartmentAutocomplete(autocomplete.Select2QuerySetView):
          def get_queryset(self):
              qs = Department.objects.all()
              term = (self.q or "").strip()
              if term:
                  qs = qs.filter(name__icontains=term)
              return qs.order_by("name")


      @admin.register(Company)
      class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
          reverse_relations = {
              "department_binding": ReverseRelationConfig(
                  model=Department,
                  fk_field="company",
                  widget=autocomplete.ModelSelect2(
                      url="department-autocomplete", attrs={"data-minimum-input-length": 2}
                  ),
                  limit_choices_to=company_department_queryset,
              )
          }

.. dropdown:: Example: django-unfold

   Override the default widgets to match your admin theme, for example
   when using `django-unfold <https://github.com/unfoldadmin/django-unfold>`_.

   .. note::
      These examples require ``django-unfold`` to be installed and configured
      in your project.

   .. tab-set::

      .. tab-item:: SelectWidget

         Override the default ``forms.Select`` with Unfold's styled version.

         .. code-block:: python

            from unfold.widgets import UnfoldAdminSelectWidget

            @admin.register(Company)
            class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                reverse_relations = {
                    "department_binding": ReverseRelationConfig(
                        model=Department,
                        fk_field="company",
                        widget=UnfoldAdminSelectWidget(),
                    )
                }

      .. tab-item:: Select2Widget

         Use Unfold's ``Select2`` widget for a better user experience.

         .. code-block:: python

            from unfold.widgets import UnfoldAdminSelect2Widget

            @admin.register(Company)
            class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                reverse_relations = {
                    "department_binding": ReverseRelationConfig(
                        model=Department,
                        fk_field="company",
                        widget=UnfoldAdminSelect2Widget(),
                    )
                }
