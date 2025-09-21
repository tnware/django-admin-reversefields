from django.contrib import admin

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

from .models import Extension, Service, Site


@admin.register(Service)
class ServiceAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
    reverse_relations = {
        "site_binding": ReverseRelationConfig(
            model=Site,
            fk_field="service",
            label="Site",
        ),
        "assigned_extensions": ReverseRelationConfig(
            model=Extension,
            fk_field="service",
            label="Extensions",
            multiple=True,
            ordering=("number",),
        ),
    }

    fieldsets = (("Binding", {"fields": ("site_binding", "assigned_extensions")}),)
