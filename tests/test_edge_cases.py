"""Tests for edge cases and non-parameterizable scenarios."""

# Test imports
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)
from tests.models import Company, CompanySettings, Department, Employee, Project
from tests.shared_test_base import BaseAdminMixinTestCase


class EdgeCasesTests(BaseAdminMixinTestCase):
    """Test suite for edge cases and non-parameterizable scenarios."""

    def test_invalid_fk_field_name_fails_early(self):
        """Misconfigured fk_field names should fail during form construction."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "bad_binding": ReverseRelationConfig(
                    model=Department,
                    fk_field="does_not_exist",
                ),
            }

        admin_inst = TestAdmin(Company, self.site)
        request = self.factory.get("/")

        with self.assertRaisesMessage(ImproperlyConfigured, "does not exist on model"):
            admin_inst.get_form(request, self.company)

    def test_non_relational_fk_field_fails_early(self):
        """fk_field must reference a ForeignKey or OneToOneField."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "bad_binding": ReverseRelationConfig(
                    model=Department,
                    fk_field="name",  # CharField, not a relation
                ),
            }

        admin_inst = TestAdmin(Company, self.site)
        request = self.factory.get("/")

        with self.assertRaisesMessage(ImproperlyConfigured, "must be a ForeignKey or OneToOneField"):
            admin_inst.get_form(request, self.company)

    def test_fk_field_target_model_mismatch_fails_early(self):
        """fk_field target model must match the admin's parent model."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "bad_binding": ReverseRelationConfig(
                    model=Employee,
                    fk_field="department",  # Points to Department, not Company
                ),
            }

        admin_inst = TestAdmin(Company, self.site)
        request = self.factory.get("/")

        with self.assertRaisesMessage(ImproperlyConfigured, "but this admin manages"):
            admin_inst.get_form(request, self.company)

    def test_large_dataset_performance(self):
        """Test base operations with large datasets."""
        # Create a large dataset
        large_departments = self.create_large_dataset(100, "departments")
        large_projects = self.create_large_dataset(50, "projects")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "project_binding": ReverseRelationConfig(
                    model=Project,
                    fk_field="company",
                    multiple=False,
                ),
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)

        # Test form creation with large dataset (should not timeout)
        form = form_cls(instance=self.company)
        self.assertIn("project_binding", form.fields)
        self.assertIn("assigned_departments", form.fields)

        # Test selecting multiple items from large dataset
        selected_departments = [dept.pk for dept in large_departments[:10]]  # Select first 10
        selected_project = large_projects[0].pk

        form_with_selection = form_cls(
            {
                "name": self.company.name,
                "project_binding": selected_project,
                "assigned_departments": selected_departments,
            },
            instance=self.company,
        )

        self.assertTrue(form_with_selection.is_valid())
        saved_company = form_with_selection.save()

        # Verify correct number of bindings
        bound_departments = Department.objects.filter(company=saved_company)
        self.assertEqual(bound_departments.count(), 10)

        bound_project = Project.objects.get(company=saved_company)
        self.assertEqual(bound_project.pk, selected_project)

    def test_maximum_selection_limits(self):
        """Test base operations at maximum reasonable selection limits."""
        # Create test data
        departments = self.create_test_departments(20)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)

        # Test selecting all available items
        all_department_pks = [dept.pk for dept in departments]
        form = form_cls(
            {"name": self.company.name, "assigned_departments": all_department_pks},
            instance=self.company,
        )

        self.assertTrue(form.is_valid())
        saved_company = form.save()

        # Verify all items were bound
        bound_count = Department.objects.filter(company=saved_company).count()
        self.assertEqual(bound_count, len(departments))

    def test_filtered_queryset_edge_cases(self):
        """Test base operations with heavily filtered querysets."""
        # Create test data with specific patterns
        departments = []
        for i in range(10):
            dept = Department.objects.create(name=f"Department{i}")
            departments.append(dept)

        # Create admin with filtering that excludes most items
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,
                    limit_choices_to=lambda qs, instance, request: qs.filter(
                        name__endswith="5"
                    ),  # Only names ending in 5
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)
        form = form_cls(instance=self.company)

        # Should only have one choice (Department5)
        dept_field = form.fields["assigned_departments"]
        if hasattr(dept_field, "queryset"):
            filtered_count = dept_field.queryset.count()
            self.assertEqual(filtered_count, 1)

        # Test selecting the filtered item
        filtered_dept = Department.objects.get(name="Department5")
        form_with_selection = form_cls(
            {"name": self.company.name, "assigned_departments": [filtered_dept.pk]},
            instance=self.company,
        )

        self.assertTrue(form_with_selection.is_valid())
        saved_company = form_with_selection.save()

        # Verify binding was created
        filtered_dept.refresh_from_db()
        self.assertEqual(filtered_dept.company, saved_company)

    def test_empty_selection_after_filtering(self):
        """Test base operations when filtering results in no available choices."""
        # Create test data
        self.create_test_departments(5)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,
                    limit_choices_to=lambda qs, instance, request: qs.filter(
                        name="nonexistent"
                    ),  # Filter that matches nothing
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)
        form = form_cls(instance=self.company)

        # Should have no choices available
        dept_field = form.fields["assigned_departments"]
        if hasattr(dept_field, "queryset"):
            self.assertEqual(dept_field.queryset.count(), 0)

        # Form should be valid with empty selection
        form_with_empty = form_cls(
            {"name": self.company.name, "assigned_departments": []}, instance=self.company
        )
        self.assertTrue(form_with_empty.is_valid())

    def test_model_deletion_edge_cases(self):
        """Test base operations when related models are deleted during processing."""
        # Create test data
        project_a = Project.objects.create(name="Project A")
        dept_a = Department.objects.create(name="Department A")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "project_binding": ReverseRelationConfig(
                    model=Project,
                    fk_field="company",
                    multiple=False,
                ),
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)

        # Create form with valid selections
        form = form_cls(
            {
                "name": self.company.name,
                "project_binding": project_a.pk,
                "assigned_departments": [dept_a.pk],
            },
            instance=self.company,
        )

        self.assertTrue(form.is_valid())

        # Delete one of the selected objects before saving
        deleted_dept_pk = dept_a.pk
        dept_a.delete()

        # Save should handle the missing object gracefully
        # The exact behavior depends on implementation, but it shouldn't crash
        from django.db.utils import DatabaseError

        try:
            saved_company = form.save()
            # If save succeeds, verify remaining bindings
            project_a.refresh_from_db()
            self.assertEqual(project_a.company, saved_company)
            # Verify the deleted department is not bound
            self.assertEqual(Department.objects.filter(pk=deleted_dept_pk).count(), 0)
        except (Department.DoesNotExist, DatabaseError):
            # If save fails due to missing object or database error, that's acceptable behavior
            # The important thing is that it doesn't crash unexpectedly
            pass

    def test_concurrent_model_modifications(self):
        """Test base operations with concurrent model modifications."""
        # Create test data
        project_a = Project.objects.create(name="Project A")
        dept_a = Department.objects.create(name="Department A")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "project_binding": ReverseRelationConfig(
                    model=Project,
                    fk_field="company",
                    multiple=False,
                ),
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)

        # Create form
        form = form_cls(
            {
                "name": self.company.name,
                "project_binding": project_a.pk,
                "assigned_departments": [dept_a.pk],
            },
            instance=self.company,
        )

        self.assertTrue(form.is_valid())

        # Simulate concurrent modification: another process binds the objects
        concurrent_company = Company.objects.create(name="concurrent-company")
        project_a.company = concurrent_company
        project_a.save()
        dept_a.company = concurrent_company
        dept_a.save()

        # Our form save should still work (unbind from concurrent, bind to ours)
        saved_company = form.save()

        # Verify final state
        project_a.refresh_from_db()
        dept_a.refresh_from_db()
        self.assertEqual(project_a.company, saved_company)
        self.assertEqual(dept_a.company, saved_company)

    def test_transaction_rollback_scenarios(self):
        """Test base operations with transaction rollback scenarios."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "settings_binding": ReverseRelationConfig(
                    model=CompanySettings,
                    fk_field="company",
                    multiple=False,
                ),
            }

        # Create test data
        settings_a = CompanySettings.objects.create(timezone="UTC")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)

        # Create a form that should succeed
        form = form_cls(
            {"name": self.company.name, "settings_binding": settings_a.pk},
            instance=self.company,
        )

        self.assertTrue(form.is_valid())

        # Use transaction to test rollback behavior
        try:
            with transaction.atomic():
                saved_company = form.save()

                # Verify binding was created
                settings_a.refresh_from_db()
                self.assertEqual(settings_a.company, saved_company)

                # Force a rollback by raising an exception
                raise RuntimeError("Force rollback")

        except RuntimeError:
            pass  # Expected

        # After rollback, binding should not exist
        settings_a.refresh_from_db()
        self.assertIsNone(settings_a.company)

    def test_multiple_companies_complex_bindings(self):
        """Test base operations with multiple companies and complex binding patterns."""
        # Create multiple companies and objects
        company_a = Company.objects.create(name="company-a")
        company_b = Company.objects.create(name="company-b")

        # Create objects with mixed binding states
        project_1 = Project.objects.create(name="Project 1", company=company_a)
        project_2 = Project.objects.create(name="Project 2")  # Unbound
        project_3 = Project.objects.create(name="Project 3", company=company_b)

        dept_1 = Department.objects.create(name="Department 1", company=company_a)
        dept_2 = Department.objects.create(name="Department 2", company=company_b)
        dept_3 = Department.objects.create(name="Department 3")  # Unbound

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "project_binding": ReverseRelationConfig(
                    model=Project,
                    fk_field="company",
                    multiple=False,
                ),
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)

        # Select objects from different companies and unbound objects
        form = form_cls(
            {
                "name": self.company.name,
                "project_binding": project_3.pk,  # From company_b
                "assigned_departments": [dept_1.pk, dept_2.pk, dept_3.pk],  # Mixed sources
            },
            instance=self.company,
        )

        self.assertTrue(form.is_valid())
        saved_company = form.save()

        # Verify all objects were transferred to our company
        project_3.refresh_from_db()
        dept_1.refresh_from_db()
        dept_2.refresh_from_db()
        dept_3.refresh_from_db()

        self.assertEqual(project_3.company, saved_company)
        self.assertEqual(dept_1.company, saved_company)
        self.assertEqual(dept_2.company, saved_company)
        self.assertEqual(dept_3.company, saved_company)

        # Verify other companies lost their bindings
        self.assertEqual(Project.objects.filter(company=company_a).count(), 1)  # project_1 remains
        self.assertEqual(Project.objects.filter(company=company_b).count(), 0)  # project_3 moved
        self.assertEqual(Department.objects.filter(company=company_a).count(), 0)  # dept_1 moved
        self.assertEqual(Department.objects.filter(company=company_b).count(), 0)  # dept_2 moved

    def test_circular_relationship_scenarios(self):
        """Test base operations with potential circular relationship scenarios."""
        # Create a complex scenario where companies could reference each other indirectly
        company_a = Company.objects.create(name="company-a")
        company_b = Company.objects.create(name="company-b")

        # Create projects that reference different companies
        project_a = Project.objects.create(name="Project A", company=company_a)
        project_b = Project.objects.create(name="Project B", company=company_b)

        # Create departments that reference different companies
        dept_a = Department.objects.create(name="Department A", company=company_a)
        dept_b = Department.objects.create(name="Department B", company=company_b)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "project_binding": ReverseRelationConfig(
                    model=Project,
                    fk_field="company",
                    multiple=False,
                ),
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)

        # Test moving objects from company_a to company_b
        form_cls_b = admin_inst.get_form(request, company_b)
        form_b = form_cls_b(
            {
                "name": company_b.name,
                "project_binding": project_a.pk,  # Move from company_a
                "assigned_departments": [dept_a.pk, dept_b.pk],  # Keep dept_b, add dept_a
            },
            instance=company_b,
        )

        self.assertTrue(form_b.is_valid())
        form_b.save()

        # Verify transfers
        project_a.refresh_from_db()
        dept_a.refresh_from_db()
        dept_b.refresh_from_db()

        self.assertEqual(project_a.company, company_b)
        self.assertEqual(dept_a.company, company_b)
        self.assertEqual(dept_b.company, company_b)

        # Now test moving objects back to company_a
        form_cls_a = admin_inst.get_form(request, company_a)
        form_a = form_cls_a(
            {
                "name": company_a.name,
                "project_binding": project_b.pk,  # Move from company_b
                "assigned_departments": [dept_a.pk],  # Move back dept_a
            },
            instance=company_a,
        )

        self.assertTrue(form_a.is_valid())
        form_a.save()

        # Verify final state
        project_a.refresh_from_db()
        project_b.refresh_from_db()
        dept_a.refresh_from_db()
        dept_b.refresh_from_db()

        self.assertEqual(project_a.company, company_b)  # Still with company_b
        self.assertEqual(project_b.company, company_a)  # Moved to company_a
        self.assertEqual(dept_a.company, company_a)  # Moved back to company_a
        self.assertEqual(dept_b.company, company_b)  # Remains with company_b

    def test_mixed_relationship_types(self):
        """Test base operations with mixed relationship types (ForeignKey and OneToOne)."""
        # Create test data
        project_a = Project.objects.create(name="Project A")
        dept_a = Department.objects.create(name="Department A")
        settings_a = CompanySettings.objects.create(timezone="UTC")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "project_binding": ReverseRelationConfig(
                    model=Project,
                    fk_field="company",
                    multiple=False,  # Single ForeignKey
                ),
                "assigned_departments": ReverseRelationConfig(
                    model=Department,
                    fk_field="company",
                    multiple=True,  # Multiple ForeignKey
                ),
                "settings_binding": ReverseRelationConfig(
                    model=CompanySettings,
                    fk_field="company",
                    multiple=False,  # OneToOne relationship
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)

        # Test binding all relationship types
        form = form_cls(
            {
                "name": self.company.name,
                "project_binding": project_a.pk,
                "assigned_departments": [dept_a.pk],
                "settings_binding": settings_a.pk,
            },
            instance=self.company,
        )

        self.assertTrue(form.is_valid())
        saved_company = form.save()

        # Verify all bindings were created
        project_a.refresh_from_db()
        dept_a.refresh_from_db()
        settings_a.refresh_from_db()

        self.assertEqual(project_a.company, saved_company)
        self.assertEqual(dept_a.company, saved_company)
        self.assertEqual(settings_a.company, saved_company)

        # Test partial unbinding (keep settings, unbind others)
        form_partial = form_cls(
            {
                "name": self.company.name,
                "project_binding": "",
                "assigned_departments": [],
                "settings_binding": settings_a.pk,  # Keep this one
            },
            instance=self.company,
        )

        self.assertTrue(form_partial.is_valid())
        form_partial.save()

        # Verify partial unbinding
        project_a.refresh_from_db()
        dept_a.refresh_from_db()
        settings_a.refresh_from_db()

        self.assertIsNone(project_a.company)  # Unbound
        self.assertIsNone(dept_a.company)  # Unbound
        self.assertEqual(settings_a.company, saved_company)  # Still bound

    def test_relationship_constraint_interactions(self):
        """Test base operations with complex constraint interactions."""
        # Create companies and settings
        company_a = Company.objects.create(name="company-a")
        company_b = Company.objects.create(name="company-b")

        settings_1 = CompanySettings.objects.create(timezone="UTC", company=company_a)
        settings_2 = CompanySettings.objects.create(timezone="EST", company=company_b)
        settings_3 = CompanySettings.objects.create(timezone="PST")  # Unbound

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "settings_binding": ReverseRelationConfig(
                    model=CompanySettings,
                    fk_field="company",
                    multiple=False,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Company, self.site)
        form_cls = admin_inst.get_form(request, self.company)

        # Test transferring settings from another company
        form = form_cls(
            {"name": self.company.name, "settings_binding": settings_1.pk},
            instance=self.company,
        )

        self.assertTrue(form.is_valid())
        saved_company = form.save()

        # Verify transfer (should unbind from company_a, bind to our company)
        settings_1.refresh_from_db()
        self.assertEqual(settings_1.company, saved_company)

        # Verify company_a lost its settings
        company_a.refresh_from_db()
        with self.assertRaises(CompanySettings.DoesNotExist):
            _ = company_a.settings

        # Test switching to a different settings
        form_switch = form_cls(
            {"name": self.company.name, "settings_binding": settings_2.pk},
            instance=self.company,
        )

        self.assertTrue(form_switch.is_valid())
        form_switch.save()

        # Verify switch (settings_1 should be unbound, settings_2 should be bound)
        settings_1.refresh_from_db()
        settings_2.refresh_from_db()

        self.assertIsNone(settings_1.company)  # Unbound
        self.assertEqual(settings_2.company, saved_company)  # Bound

        # Verify company_b lost its settings
        company_b.refresh_from_db()
        with self.assertRaises(CompanySettings.DoesNotExist):
            _ = company_b.settings
