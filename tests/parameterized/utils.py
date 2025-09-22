# Django imports
from django.contrib import admin

# Project imports
from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

# Test imports
from ..models import Company, Department, Project


def create_parameterized_admin(bulk_enabled):
    """Factory to create a TestAdmin class with parameterized bulk settings."""

    class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
        reverse_relations = {
            "department_binding": ReverseRelationConfig(
                model=Department,
                fk_field="company",
                multiple=False,
                bulk=bulk_enabled,
            ),
            "assigned_projects": ReverseRelationConfig(
                model=Project,
                fk_field="company",
                multiple=True,
                bulk=bulk_enabled,
            ),
        }

    return TestAdmin(Company, None)
