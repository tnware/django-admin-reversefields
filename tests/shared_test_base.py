"""Shared test utilities and base classes for admin mixin tests."""

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

from .models import Company, Department, Employee, Project


class DummySite(AdminSite):
    """Dummy admin site for testing purposes."""


class BaseAdminMixinTestCase(TestCase):
    """Base test case with common setup and utilities for admin mixin tests."""

    def setUp(self):
        """Set up common test fixtures."""
        self.site = DummySite()
        self.factory = RequestFactory()
        self.company = Company.objects.create(name="test-company")

    def create_test_departments(self, count=3, company=None):
        """Create test Department objects.

        Args:
            count: Number of departments to create
            company: Company to bind departments to (optional)

        Returns:
            List of created Department objects
        """
        departments = []
        for i in range(count):
            dept = Department.objects.create(name=f"Department {i + 1}", company=company)
            departments.append(dept)
        return departments

    def create_test_projects(self, count=2, company=None):
        """Create test Project objects.

        Args:
            count: Number of projects to create
            company: Company to bind projects to (optional)

        Returns:
            List of created Project objects
        """
        projects = []
        for i in range(count):
            project = Project.objects.create(
                name=f"Project {chr(65 + i)}",  # Project A, Project B, etc.
                company=company,
            )
            projects.append(project)
        return projects

    def create_test_companies(self, count=1):
        """Create test Company objects.

        Args:
            count: Number of companies to create

        Returns:
            List of created Company objects
        """
        companies = []
        for i in range(count):
            company = Company.objects.create(name=f"company-{i + 1}")
            companies.append(company)
        return companies

    def create_test_employees(self, count=2, department=None):
        """Create test Employee objects.

        Args:
            count: Number of employees to create
            department: Department to bind employees to (optional)

        Returns:
            List of created Employee objects
        """
        employees = []
        for i in range(count):
            employee = Employee.objects.create(
                name=f"Employee {i + 1}",
                email=f"employee{i + 1}@example.com",
                department=department,
            )
            employees.append(employee)
        return employees

    def create_parameterized_admin(self, bulk_enabled=False, **config_overrides):
        """Create admin with configurable bulk settings for parameterized tests.

        Args:
            bulk_enabled: Whether to enable bulk operations
            **config_overrides: Additional configuration overrides for reverse relations

        Returns:
            Admin class instance configured for testing
        """

        class ParameterizedCompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "department_binding": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    label="Department",
                    bulk=bulk_enabled,
                    **config_overrides.get("department_binding", {}),
                ),
                "assigned_projects": ReverseRelationConfig(
                    model=Project,
                    fk_field="company",
                    label="Projects",
                    multiple=True,
                    ordering=("name",),
                    bulk=bulk_enabled,
                    **config_overrides.get("assigned_projects", {}),
                ),
            }

            fieldsets = (("Binding", {"fields": ("department_binding", "assigned_projects")}),)

        return ParameterizedCompanyAdmin(Company, self.site)

    def assert_widget_compatibility(self, widget_class, field_name, admin_instance=None):
        """Assert that a widget works correctly with reverse relation fields.

        Args:
            widget_class: Widget class to test
            field_name: Name of the reverse relation field
            admin_instance: Optional admin instance (creates default if None)
        """
        if admin_instance is None:
            admin_instance = self.create_parameterized_admin()

        request = self.factory.get("/")
        form_cls = admin_instance.get_form(request, self.company)
        form = form_cls(instance=self.company)

        # Assert field exists
        self.assertIn(field_name, form.fields)

        # Assert widget is of expected type
        field = form.fields[field_name]
        self.assertIsInstance(field.widget, widget_class)

        # Assert widget renders without error
        widget_html = field.widget.render(field_name, None)
        self.assertIsInstance(widget_html, str)
        self.assertGreater(len(widget_html), 0)

    def create_permission_test_scenario(self, policy_type="allow_all"):
        """Create standardized permission test scenarios.

        Args:
            policy_type: Type of permission scenario to create
                - "allow_all": Always allow access
                - "deny_all": Always deny access
                - "staff_only": Allow only staff users
                - "callable": Function-based permission

        Returns:
            Dictionary with permission policy and test users
        """
        # Create test users
        regular_user = User.objects.create_user(username="regular", password="test", is_staff=False)
        staff_user = User.objects.create_user(username="staff", password="test", is_staff=True)

        if policy_type == "allow_all":

            def policy(request, obj, config, selection):
                return True
        elif policy_type == "deny_all":

            def policy(request, obj, config, selection):
                return False
        elif policy_type == "staff_only":

            def policy(request, obj, config, selection):
                return getattr(request.user, "is_staff", False)
        elif policy_type == "callable":

            def policy(request, obj, config, selection):
                """Custom permission policy for testing."""
                return hasattr(request.user, "username") and request.user.username.startswith(
                    "staff"
                )
        else:
            raise ValueError(f"Unknown policy_type: {policy_type}")

        return {
            "policy": policy,
            "regular_user": regular_user,
            "staff_user": staff_user,
        }

    def create_large_dataset(self, count=100, model_type="departments"):
        """Create large datasets for performance and edge case testing.

        Args:
            count: Number of objects to create
            model_type: Type of objects to create ("departments", "projects", "companies",
                "employees")

        Returns:
            List of created objects
        """
        objects = []

        if model_type == "departments":
            for i in range(count):
                dept = Department.objects.create(name=f"Bulk Department {i:04d}")
                objects.append(dept)
        elif model_type == "projects":
            for i in range(count):
                project = Project.objects.create(name=f"Bulk Project {i:04d}")
                objects.append(project)
        elif model_type == "companies":
            for i in range(count):
                company = Company.objects.create(name=f"bulk-company-{i:04d}")
                objects.append(company)
        elif model_type == "employees":
            for i in range(count):
                employee = Employee.objects.create(
                    name=f"Bulk Employee {i:04d}", email=f"bulk{i:04d}@example.com"
                )
                objects.append(employee)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        return objects

    def create_edge_case_data(self, scenario="empty_queryset"):
        """Create various edge case data scenarios for testing.

        Args:
            scenario: Type of edge case to create
                - "empty_queryset": No related objects available
                - "single_item": Only one related object available
                - "max_items": Maximum reasonable number of items
                - "invalid_data": Data that should cause validation errors
                - "complex_relationships": Complex model relationship scenarios

        Returns:
            Dictionary with scenario data and metadata
        """
        if scenario == "empty_queryset":
            # Clear all existing objects
            Department.objects.all().delete()
            Project.objects.all().delete()
            return {"departments": [], "projects": [], "description": "No objects available"}

        elif scenario == "single_item":
            # Create exactly one of each type
            Department.objects.all().delete()
            Project.objects.all().delete()
            dept = Department.objects.create(name="Single Department")
            project = Project.objects.create(name="Single Project")
            return {
                "departments": [dept],
                "projects": [project],
                "description": "Single item available",
            }

        elif scenario == "max_items":
            # Create a large but reasonable number of items
            departments = self.create_large_dataset(50, "departments")
            projects = self.create_large_dataset(25, "projects")
            return {
                "departments": departments,
                "projects": projects,
                "description": "Maximum reasonable items",
            }

        elif scenario == "invalid_data":
            # Create data that should cause validation issues
            return {
                "invalid_pks": [99999, -1, "invalid"],
                "empty_strings": ["", None],
                "description": "Invalid data for validation testing",
            }

        elif scenario == "complex_relationships":
            # Create complex relationship scenarios
            company1 = Company.objects.create(name="complex-company-1")
            company2 = Company.objects.create(name="complex-company-2")

            # Departments bound to different companies
            dept1 = Department.objects.create(name="Complex Dept 1", company=company1)
            dept2 = Department.objects.create(name="Complex Dept 2", company=company2)
            dept3 = Department.objects.create(name="Complex Dept 3")  # Unbound

            # Projects with mixed binding states
            project1 = Project.objects.create(name="Complex Project 1", company=company1)
            project2 = Project.objects.create(name="Complex Project 2")  # Unbound

            return {
                "companies": [company1, company2],
                "departments": [dept1, dept2, dept3],
                "projects": [project1, project2],
                "bound_departments": [dept1, dept2],
                "unbound_departments": [dept3],
                "bound_projects": [project1],
                "unbound_projects": [project2],
                "description": "Complex relationship scenarios",
            }

        else:
            raise ValueError(f"Unknown scenario: {scenario}")

    def create_widget_test_data(self, widget_type="select"):
        """Create test data optimized for widget compatibility testing.

        Args:
            widget_type: Type of widget being tested
                - "select": Single select widget
                - "radio": Radio select widget
                - "multiple": Multiple select widget
                - "checkbox": Checkbox multiple select widget

        Returns:
            Dictionary with test data and expected behaviors
        """
        # Create base test data
        departments = self.create_test_departments(5)
        projects = self.create_test_projects(3)

        if widget_type in ["select", "radio"]:
            return {
                "departments": departments,
                "projects": projects,
                "expected_single_select": True,
                "expected_multiple_select": False,
                "test_selections": [departments[0].pk, projects[0].pk],
                "description": f"Data for {widget_type} widget testing",
            }

        elif widget_type in ["multiple", "checkbox"]:
            return {
                "departments": departments,
                "projects": projects,
                "expected_single_select": False,
                "expected_multiple_select": True,
                "test_selections": [
                    [departments[0].pk, departments[1].pk],
                    [projects[0].pk, projects[1].pk],
                ],
                "description": f"Data for {widget_type} widget testing",
            }

        else:
            raise ValueError(f"Unknown widget_type: {widget_type}")

    def create_validation_test_scenarios(self):
        """Create comprehensive validation test scenarios.

        Returns:
            Dictionary with various validation scenarios
        """
        # Create base data
        company = Company.objects.create(name="validation-company")
        departments = self.create_test_departments(3)
        projects = self.create_test_projects(2)

        return {
            "valid_single_selection": projects[0].pk,
            "valid_multiple_selection": [departments[0].pk, departments[1].pk],
            "invalid_pk": 99999,
            "invalid_type": "not-a-number",
            "empty_selection": None,
            "empty_multiple_selection": [],
            "mixed_valid_invalid": [departments[0].pk, 99999],
            "company": company,
            "departments": departments,
            "projects": projects,
            "description": "Comprehensive validation scenarios",
        }
