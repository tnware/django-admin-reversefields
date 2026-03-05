"""
Admin configurations following quickstart documentation patterns.
"""

# Required imports from quickstart guide
from django.contrib import admin

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

from .models import Assignment, Company, CompanySettings, Department, Employee, Project


@admin.register(Company)
class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
    """
    Company admin following quickstart patterns.

    Following the quickstart guide step-by-step:
    1. Inherit from ReverseRelationAdminMixin and admin.ModelAdmin
    2. Declare reverse_relations dict with virtual field names as keys
    3. Include virtual field names in fieldsets
    """

    # Step 1: Declare reverse_relations dict keyed by virtual field name
    reverse_relations = {
        # Multi-select: manage which departments belong to this company
        "departments": ReverseRelationConfig(
            model=Department,
            fk_field="company",
            multiple=True,
        ),
        # Multi-select: manage which projects belong to this company
        "projects": ReverseRelationConfig(
            model=Project,
            fk_field="company",
            multiple=True,
        ),
        # Single-select: bind one CompanySettings instance (OneToOne)
        "settings": ReverseRelationConfig(
            model=CompanySettings,
            fk_field="company",
            multiple=False,
        ),
    }

    # Step 2: Include virtual field names in fieldsets as instructed
    fieldsets = (
        ("Company Information", {"fields": ("name", "founded_year")}),
        ("Departments & Projects", {"fields": ("departments", "projects")}),
        ("Settings", {"fields": ("settings",)}),
    )


@admin.register(Department)
class DepartmentAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
    """
    Department admin following quickstart patterns.

    Following the same pattern as CompanyAdmin but for Department model.
    """

    # Following the same pattern: dict keyed by virtual field name
    reverse_relations = {
        # Multi-select: manage all employees assigned to this department
        "employees": ReverseRelationConfig(
            model=Employee,
            fk_field="department",
            multiple=True,
        ),
    }

    # Include virtual field names in fieldsets
    fieldsets = (
        ("Department Information", {"fields": ("name", "company", "budget")}),
        ("Staff", {"fields": ("employees",)}),
    )


# Basic admin registrations for other models (no reverse relationships needed for this task)
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Basic admin for Employee model."""

    list_display = ("name", "email", "department", "hire_date")
    list_filter = ("department", "hire_date")
    search_fields = ("name", "email")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Basic admin for Project model."""

    list_display = ("name", "company", "is_active", "start_date", "end_date")
    list_filter = ("company", "is_active", "start_date")
    search_fields = ("name",)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    """Basic admin for Assignment model."""

    list_display = ("employee", "project", "role", "hours_allocated", "start_date")
    list_filter = ("role", "project__company", "start_date")
    search_fields = ("employee__name", "project__name", "role")


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    """Basic admin for CompanySettings model."""

    list_display = ("company", "timezone", "fiscal_year_start", "allow_remote_work")
    list_filter = ("timezone", "allow_remote_work")
