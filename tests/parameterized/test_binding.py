"""Parameterized tests for binding operations."""

# Test imports
from django.contrib import admin

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

from ..models import Company, Department, Project
from ..shared_test_base import BaseAdminMixinTestCase
from .utils import create_parameterized_admin


class ParameterizedBindingTests(BaseAdminMixinTestCase):
    """Test core binding operations with both bulk=True and bulk=False."""

    def test_single_select_binding_both_modes(self):
        """Test single-select binding works consistently in both bulk and non-bulk modes."""
        # Create test data
        dept_a = Department.objects.create(name="Department A")
        dept_b = Department.objects.create(name="Department B")

        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create fresh company for each test
                company = Company.objects.create(name=f"test-company-{bulk_enabled}")

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)

                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, company)

                # Test initial binding
                form = form_cls(
                    {"name": company.name, "department_binding": dept_a.pk}, instance=company
                )
                self.assertTrue(form.is_valid(), f"Form should be valid for bulk={bulk_enabled}")
                obj = form.save()

                # Verify binding worked
                dept_a.refresh_from_db()
                self.assertEqual(
                    dept_a.company, obj, f"Department A should be bound for bulk={bulk_enabled}"
                )

                # Test changing binding
                form = form_cls(
                    {"name": company.name, "department_binding": dept_b.pk}, instance=obj
                )
                self.assertTrue(
                    form.is_valid(), f"Form should be valid for rebinding with bulk={bulk_enabled}"
                )
                obj = form.save()

                # Verify rebinding worked
                dept_a.refresh_from_db()
                dept_b.refresh_from_db()
                self.assertIsNone(
                    dept_a.company, f"Department A should be unbound for bulk={bulk_enabled}"
                )
                self.assertEqual(
                    dept_b.company, obj, f"Department B should be bound for bulk={bulk_enabled}"
                )

    def test_multiple_select_binding_both_modes(self):
        """Test multi-select binding works consistently in both bulk and non-bulk modes."""
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create fresh test data for each iteration
                project_1 = Project.objects.create(name=f"Project-{bulk_enabled}-1")
                project_2 = Project.objects.create(name=f"Project-{bulk_enabled}-2")
                project_3 = Project.objects.create(name=f"Project-{bulk_enabled}-3")
                company = Company.objects.create(name=f"test-company-multi-{bulk_enabled}")

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)

                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, company)

                # Test initial multi-binding
                form = form_cls(
                    {"name": company.name, "assigned_projects": [project_1.pk, project_2.pk]},
                    instance=company,
                )
                self.assertTrue(
                    form.is_valid(),
                    f"Form should be valid for multi-select with bulk={bulk_enabled}",
                )
                obj = form.save()

                # Verify multi-binding worked
                project_1.refresh_from_db()
                project_2.refresh_from_db()
                project_3.refresh_from_db()
                self.assertEqual(
                    project_1.company, obj, f"Project 1 should be bound for bulk={bulk_enabled}"
                )
                self.assertEqual(
                    project_2.company, obj, f"Project 2 should be bound for bulk={bulk_enabled}"
                )
                self.assertIsNone(
                    project_3.company, f"Project 3 should be unbound for bulk={bulk_enabled}"
                )

                # Test changing multi-selection
                form = form_cls(
                    {"name": company.name, "assigned_projects": [project_2.pk, project_3.pk]},
                    instance=obj,
                )
                self.assertTrue(
                    form.is_valid(),
                    f"Form should be valid for multi-rebinding with bulk={bulk_enabled}",
                )
                obj = form.save()

                # Verify multi-rebinding worked
                project_1.refresh_from_db()
                project_2.refresh_from_db()
                project_3.refresh_from_db()
                self.assertIsNone(
                    project_1.company, f"Project 1 should be unbound for bulk={bulk_enabled}"
                )
                self.assertEqual(
                    project_2.company, obj, f"Project 2 should remain bound for bulk={bulk_enabled}"
                )
                self.assertEqual(
                    project_3.company,
                    obj,
                    f"Project 3 should be newly bound for bulk={bulk_enabled}",
                )

    def test_empty_selection_handling_both_modes(self):
        """Test empty selection handling works consistently in both modes."""
        # Create test data
        dept_a = Department.objects.create(name="Department A")
        project_1 = Project.objects.create(name="Project 1")

        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create fresh company for each test
                company = Company.objects.create(name=f"test-company-empty-{bulk_enabled}")

                # Initially bind objects
                dept_a.company = company
                dept_a.save()
                project_1.company = company
                project_1.save()

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)

                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, company)

                # Test clearing single-select
                form = form_cls({"name": company.name, "department_binding": ""}, instance=company)
                self.assertTrue(
                    form.is_valid(),
                    f"Form should be valid for empty single-select with bulk={bulk_enabled}",
                )
                obj = form.save()

                # Verify unbinding worked
                dept_a.refresh_from_db()
                self.assertIsNone(
                    dept_a.company, f"Department should be unbound for bulk={bulk_enabled}"
                )

                # Test clearing multi-select
                form = form_cls({"name": company.name, "assigned_projects": []}, instance=obj)
                self.assertTrue(
                    form.is_valid(),
                    f"Form should be valid for empty multi-select with bulk={bulk_enabled}",
                )
                obj = form.save()

                # Verify multi-unbinding worked
                project_1.refresh_from_db()
                self.assertIsNone(
                    project_1.company, f"Project should be unbound for bulk={bulk_enabled}"
                )

    def test_empty_queryset_handling_both_modes(self):
        """Test operations with completely empty querysets in both modes."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                Department.objects.all().delete()
                Project.objects.all().delete()

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.company)
                form = form_cls(instance=self.company)

                self.assertIn("department_binding", form.fields)
                self.assertIn("assigned_projects", form.fields)

                dept_field = form.fields["department_binding"]
                proj_field = form.fields["assigned_projects"]

                if hasattr(dept_field, "queryset"):
                    self.assertEqual(dept_field.queryset.count(), 0)
                if hasattr(proj_field, "queryset"):
                    self.assertEqual(proj_field.queryset.count(), 0)

                form_data = {
                    "name": self.company.name,
                    "department_binding": "",
                    "assigned_projects": [],
                }
                form_with_data = form_cls(form_data, instance=self.company)
                self.assertTrue(form_with_data.is_valid())

    def test_limit_choices_to_dict_both_modes(self):
        """Static dict limiters filter choices as expected in both modes."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                other_company = Company.objects.create(name=f"other-{bulk_enabled}")
                unbound = Project.objects.create(name=f"free-{bulk_enabled}")
                bound_elsewhere = Project.objects.create(name=f"busy-{bulk_enabled}", company=other_company)

                class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                    reverse_relations = {
                        "assigned_projects": ReverseRelationConfig(
                            model=Project,
                            fk_field="company",
                            multiple=True,
                            bulk=bulk_enabled,
                            limit_choices_to={"company__isnull": True},
                        )
                    }

                admin_instance = TestAdmin(Company, self.site)
                request = self.factory.get("/")
                form_cls = admin_instance.get_form(request, self.company)
                form = form_cls(instance=self.company)

                field = form.fields["assigned_projects"]
                # Only the unbound project should be offered by the static dict limiter
                if hasattr(field, "queryset"):
                    self.assertEqual(list(field.queryset.values_list("pk", flat=True)), [unbound.pk])

                # Selecting the unbound project is valid and should bind it
                form_select = form_cls(
                    {"name": self.company.name, "assigned_projects": [unbound.pk]},
                    instance=self.company,
                )
                self.assertTrue(form_select.is_valid())
                saved_company = form_select.save()

                unbound.refresh_from_db()
                bound_elsewhere.refresh_from_db()
                self.assertEqual(unbound.company, saved_company)
                self.assertEqual(bound_elsewhere.company, other_company)

    def test_single_item_selection_edge_cases_both_modes(self):
        """Test operations with exactly one item available in both modes."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                Department.objects.all().delete()
                Project.objects.all().delete()

                single_project = Project.objects.create(name="Only Project")
                single_dept = Department.objects.create(name="Only Department")

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.company)

                form = form_cls(
                    {
                        "name": self.company.name,
                        "department_binding": single_dept.pk,
                        "assigned_projects": [single_project.pk],
                    },
                    instance=self.company,
                )

                self.assertTrue(form.is_valid())
                saved_company = form.save()

                single_project.refresh_from_db()
                single_dept.refresh_from_db()
                self.assertEqual(single_project.company, saved_company)
                self.assertEqual(single_dept.company, saved_company)

                form_deselect = form_cls(
                    {"name": self.company.name, "department_binding": "", "assigned_projects": []},
                    instance=self.company,
                )

                self.assertTrue(form_deselect.is_valid())
                form_deselect.save()

                single_project.refresh_from_db()
                single_dept.refresh_from_db()
                self.assertIsNone(single_project.company)
                self.assertIsNone(single_dept.company)

    def test_pre_existing_bindings_both_modes(self):
        """Test operations when objects already have existing bindings in both modes."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                other_company = Company.objects.create(name="other-company")

                project_a = Project.objects.create(name="Project A", company=other_company)
                project_b = Project.objects.create(name="Project B")  # Unbound
                dept_a = Department.objects.create(name="Department A", company=other_company)
                dept_b = Department.objects.create(name="Department B")  # Unbound

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.company)

                form = form_cls(
                    {
                        "name": self.company.name,
                        "department_binding": dept_a.pk,  # Currently bound to other_company
                        "assigned_projects": [project_a.pk, project_b.pk],
                    },
                    instance=self.company,
                )

                self.assertTrue(form.is_valid())
                saved_company = form.save()

                project_a.refresh_from_db()
                project_b.refresh_from_db()
                dept_a.refresh_from_db()
                dept_b.refresh_from_db()

                self.assertEqual(project_a.company, saved_company)
                self.assertEqual(project_b.company, saved_company)
                self.assertEqual(dept_a.company, saved_company)
                self.assertEqual(Department.objects.filter(company=other_company).count(), 0)

    def test_model_creation_vs_update_scenarios_both_modes(self):
        """Test operations in both model creation and update scenarios in both modes."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                project_a = Project.objects.create(name="Project A")
                project_b = Project.objects.create(name="Project B")
                dept_a = Department.objects.create(name="Department A")
                dept_b = Department.objects.create(name="Department B")

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)
                request = self.factory.post("/")

                # Test creation scenario
                new_company = Company(name="new-company")
                form_cls_create = admin_instance.get_form(request, new_company)
                form_create = form_cls_create(
                    {
                        "name": new_company.name,
                        "department_binding": dept_a.pk,
                        "assigned_projects": [project_a.pk],
                    },
                    instance=new_company,
                )

                self.assertTrue(form_create.is_valid())
                created_company = form_create.save()

                project_a.refresh_from_db()
                dept_a.refresh_from_db()
                self.assertEqual(project_a.company, created_company)
                self.assertEqual(dept_a.company, created_company)

                # Test update scenario
                form_cls_update = admin_instance.get_form(request, created_company)
                form_update = form_cls_update(
                    {
                        "name": created_company.name,
                        "department_binding": dept_b.pk,
                        "assigned_projects": [project_b.pk],
                    },
                    instance=created_company,
                )

                self.assertTrue(form_update.is_valid())
                updated_company = form_update.save()

                project_a.refresh_from_db()
                project_b.refresh_from_db()
                dept_a.refresh_from_db()
                dept_b.refresh_from_db()

                self.assertIsNone(project_a.company)
                self.assertEqual(project_b.company, updated_company)
                self.assertIsNone(dept_a.company)
                self.assertEqual(dept_b.company, updated_company)

    def test_unsaved_model_instance_both_modes(self):
        """Test operations with unsaved model instances in both modes."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                unsaved_company = Company(name="unsaved-company")

                project_a = Project.objects.create(name="Project A")
                dept_a = Department.objects.create(name="Department A")

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, unsaved_company)

                form = form_cls(
                    {
                        "name": unsaved_company.name,
                        "department_binding": dept_a.pk,
                        "assigned_projects": [project_a.pk],
                    },
                    instance=unsaved_company,
                )

                self.assertTrue(form.is_valid())

                saved_company = form.save()
                self.assertIsNotNone(saved_company.pk)

                project_a.refresh_from_db()
                dept_a.refresh_from_db()
                self.assertEqual(project_a.company, saved_company)
                self.assertEqual(dept_a.company, saved_company)

    def test_commit_false_defers_reverse_updates_until_save_model_both_modes(self):
        """Reverse updates should be deferred on commit=False and applied in save_model."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                project = Project.objects.create(name=f"Deferred Project {bulk_enabled}")
                department = Department.objects.create(name=f"Deferred Department {bulk_enabled}")

                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.company)
                form = form_cls(
                    {
                        "name": self.company.name,
                        "department_binding": department.pk,
                        "assigned_projects": [project.pk],
                    },
                    instance=self.company,
                )

                self.assertTrue(form.is_valid())

                obj = form.save(commit=False)

                # Reverse relations should not be applied yet.
                project.refresh_from_db()
                department.refresh_from_db()
                self.assertIsNone(project.company)
                self.assertIsNone(department.company)
                self.assertIsNotNone(form._reverse_relation_data)

                admin_instance.save_model(request, obj, form, change=True)

                # Deferred payload should now be applied.
                project.refresh_from_db()
                department.refresh_from_db()
                self.assertEqual(project.company, obj)
                self.assertEqual(department.company, obj)
                self.assertIsNone(form._reverse_relation_data)

    def test_single_select_resubmit_same_value_both_modes(self):
        """Re-submitting the same single-select value should remain bound after save."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                department = Department.objects.create(name=f"Same Selection {bulk_enabled}")
                admin_instance = create_parameterized_admin(bulk_enabled=bulk_enabled)
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.company)

                first_submit = form_cls(
                    {"name": self.company.name, "department_binding": department.pk},
                    instance=self.company,
                )
                self.assertTrue(first_submit.is_valid())
                saved_company = first_submit.save()

                second_submit = form_cls(
                    {"name": self.company.name, "department_binding": department.pk},
                    instance=saved_company,
                )
                self.assertTrue(second_submit.is_valid())
                second_submit.save()

                department.refresh_from_db()
                self.assertEqual(department.company, saved_company)
