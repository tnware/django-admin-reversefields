"""Parameterized tests for validation handling."""

# Django imports
from django import forms
from django.contrib import admin

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

from ..models import Company, Department, Project

# Test imports
from ..shared_test_base import BaseAdminMixinTestCase
from .utils import create_parameterized_admin


class ParameterizedValidationTests(BaseAdminMixinTestCase):
    """Test validation scenarios work consistently in both bulk and non-bulk modes."""

    admin_class = admin.ModelAdmin

    def setUp(self):
        super().setUp()
        self.dept_engineering = Department.objects.create(name="Engineering", budget=500000.00)
        self.dept_marketing = Department.objects.create(name="Marketing", budget=200000.00)

    def test_required_field_validation_both_modes(self):
        """Test required field validation works consistently in both modes."""
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create admin with required field
                class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_relations = {
                        "department_binding": ReverseRelationConfig(
                            model=Department,
                            fk_field="company",
                            multiple=False,
                            bulk=bulk_enabled,
                            required=True,
                        )
                    }

                admin_instance = TestAdmin(Company, self.site)

                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.company)

                # Test with empty required field
                form = form_cls(
                    {"name": self.company.name, "department_binding": ""}, instance=self.company
                )

                # Form should be invalid for required field
                self.assertFalse(
                    form.is_valid(),
                    f"Form should be invalid for empty required field with bulk={bulk_enabled}",
                )
                self.assertIn(
                    "department_binding",
                    form.errors,
                    f"department_binding should have validation error with bulk={bulk_enabled}",
                )

    def test_invalid_pk_validation_both_modes(self):
        """Test invalid primary key validation works consistently in both modes."""
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)

                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.company)

                # Test with invalid primary key
                form = form_cls(
                    {"name": self.company.name, "department_binding": 99999}, instance=self.company
                )

                # Form should be invalid for non-existent PK
                self.assertFalse(
                    form.is_valid(),
                    f"Form should be invalid for non-existent PK with bulk={bulk_enabled}",
                )

    def test_invalid_selection_validation_both_modes(self):
        """Test invalid selection validation works consistently in both modes."""
        # Create test data
        project_1 = Project.objects.create(name="Project 1")

        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)

                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.company)

                # Test with mixed valid and invalid PKs in multi-select
                form = form_cls(
                    {"name": self.company.name, "assigned_projects": [project_1.pk, 99999]},
                    instance=self.company,
                )

                # Form should be invalid for mixed valid/invalid PKs
                self.assertFalse(
                    form.is_valid(),
                    f"Form should be invalid for mixed valid/invalid PKs with bulk={bulk_enabled}",
                )

    def test_validation_hook_both_modes(self):
        """
        Test validation hook behavior with bulk=False following documented examples.
        """
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):

                def department_validation(instance, selection, request):
                    """Custom validation following documented signature."""
                    if selection and hasattr(selection, "budget"):
                        if selection.budget and selection.budget > 300000:
                            raise forms.ValidationError(
                                "Department budget too high for this company"
                            )

                class CompanyAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_relations = {
                        "primary_department": ReverseRelationConfig(
                            model=Department,
                            fk_field="company",
                            multiple=False,
                            bulk=bulk_enabled,
                            clean=department_validation,
                        )
                    }

                request = self.factory.post("/")
                admin_inst = CompanyAdmin(Company, self.site)
                form_cls = admin_inst.get_form(request, self.company)

                # Test with low-budget department (should pass validation)
                form_valid = form_cls(
                    {"name": self.company.name, "primary_department": self.dept_marketing.pk},
                    instance=self.company,
                )
                self.assertTrue(form_valid.is_valid())

                # Test with high-budget department (should fail validation)
                form_invalid = form_cls(
                    {"name": self.company.name, "primary_department": self.dept_engineering.pk},
                    instance=self.company,
                )
                self.assertFalse(form_invalid.is_valid())
                self.assertIn("primary_department", form_invalid.errors)
                self.assertIn(
                    "budget too high", form_invalid.errors["primary_department"][0].lower()
                )
