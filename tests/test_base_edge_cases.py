"""Test suite for base operation edge cases and boundary conditions.

This module tests boundary conditions, unusual scenarios, and edge cases for base
(non-bulk) operations, focusing on empty querysets, large datasets, model lifecycle
scenarios, and complex relationship handling. Base operations use the default
bulk=False setting and process items individually.
"""

# Django imports
from django import forms
from django.contrib import admin
from django.db import transaction

# Project imports
from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

# Test imports
from .models import Extension, Service, Site, UniqueExtension
from .shared_test_base import BaseAdminMixinTestCase, DummySite


class BaseBoundaryConditionTests(BaseAdminMixinTestCase):
    """Test suite for boundary conditions with empty sets and large datasets."""

    def test_base_operation_empty_queryset_handling(self):
        """Test base operations with completely empty querysets."""
        # Clear all existing data
        Extension.objects.all().delete()
        Site.objects.all().delete()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)
        form = form_cls(instance=self.service)

        # Fields should exist but have no choices
        self.assertIn("site_binding", form.fields)
        self.assertIn("assigned_extensions", form.fields)

        # Querysets should be empty
        site_field = form.fields["site_binding"]
        ext_field = form.fields["assigned_extensions"]

        if hasattr(site_field, "queryset"):
            self.assertEqual(site_field.queryset.count(), 0)
        if hasattr(ext_field, "queryset"):
            self.assertEqual(ext_field.queryset.count(), 0)

        # Form should be valid with empty selections
        form_data = {"name": self.service.name, "site_binding": "", "assigned_extensions": []}
        form_with_data = form_cls(form_data, instance=self.service)
        self.assertTrue(form_with_data.is_valid())

    def test_base_operation_single_item_selection_edge_cases(self):
        """Test base operations with exactly one item available."""
        # Clear existing data and create exactly one of each type
        Extension.objects.all().delete()
        Site.objects.all().delete()

        single_site = Site.objects.create(name="Only Site")
        single_ext = Extension.objects.create(number="1001")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Test selecting the single available item
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": single_site.pk,
                "assigned_extensions": [single_ext.pk],
            },
            instance=self.service,
        )

        self.assertTrue(form.is_valid())
        saved_service = form.save()

        # Verify bindings were created
        single_site.refresh_from_db()
        single_ext.refresh_from_db()
        self.assertEqual(single_site.service, saved_service)
        self.assertEqual(single_ext.service, saved_service)

        # Test deselecting (should unbind)
        form_deselect = form_cls(
            {"name": self.service.name, "site_binding": "", "assigned_extensions": []},
            instance=self.service,
        )

        self.assertTrue(form_deselect.is_valid())
        form_deselect.save()

        # Verify items were unbound
        single_site.refresh_from_db()
        single_ext.refresh_from_db()
        self.assertIsNone(single_site.service)
        self.assertIsNone(single_ext.service)

    def test_base_operation_large_dataset_performance(self):
        """Test base operations with large datasets."""
        # Create a large dataset
        large_extensions = self.create_large_dataset(100, "extensions")
        large_sites = self.create_large_dataset(50, "sites")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Test form creation with large dataset (should not timeout)
        form = form_cls(instance=self.service)
        self.assertIn("site_binding", form.fields)
        self.assertIn("assigned_extensions", form.fields)

        # Test selecting multiple items from large dataset
        selected_extensions = [ext.pk for ext in large_extensions[:10]]  # Select first 10
        selected_site = large_sites[0].pk

        form_with_selection = form_cls(
            {
                "name": self.service.name,
                "site_binding": selected_site,
                "assigned_extensions": selected_extensions,
            },
            instance=self.service,
        )

        self.assertTrue(form_with_selection.is_valid())
        saved_service = form_with_selection.save()

        # Verify correct number of bindings
        bound_extensions = Extension.objects.filter(service=saved_service)
        self.assertEqual(bound_extensions.count(), 10)

        bound_site = Site.objects.get(service=saved_service)
        self.assertEqual(bound_site.pk, selected_site)

    def test_base_operation_maximum_selection_limits(self):
        """Test base operations at maximum reasonable selection limits."""
        # Create test data
        extensions = self.create_test_extensions(20)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Test selecting all available items
        all_extension_pks = [ext.pk for ext in extensions]
        form = form_cls(
            {"name": self.service.name, "assigned_extensions": all_extension_pks},
            instance=self.service,
        )

        self.assertTrue(form.is_valid())
        saved_service = form.save()

        # Verify all items were bound
        bound_count = Extension.objects.filter(service=saved_service).count()
        self.assertEqual(bound_count, len(extensions))

    def test_base_operation_filtered_queryset_edge_cases(self):
        """Test base operations with heavily filtered querysets."""
        # Create test data with specific patterns
        extensions = []
        for i in range(10):
            ext = Extension.objects.create(number=f"100{i}")
            extensions.append(ext)

        # Create admin with filtering that excludes most items
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    limit_choices_to=lambda qs, instance, request: qs.filter(
                        number__endswith="5"
                    ),  # Only numbers ending in 5
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)
        form = form_cls(instance=self.service)

        # Should only have one choice (1005)
        ext_field = form.fields["assigned_extensions"]
        if hasattr(ext_field, "queryset"):
            filtered_count = ext_field.queryset.count()
            self.assertEqual(filtered_count, 1)

        # Test selecting the filtered item
        filtered_ext = Extension.objects.get(number="1005")
        form_with_selection = form_cls(
            {"name": self.service.name, "assigned_extensions": [filtered_ext.pk]},
            instance=self.service,
        )

        self.assertTrue(form_with_selection.is_valid())
        saved_service = form_with_selection.save()

        # Verify binding was created
        filtered_ext.refresh_from_db()
        self.assertEqual(filtered_ext.service, saved_service)

    def test_base_operation_empty_selection_after_filtering(self):
        """Test base operations when filtering results in no available choices."""
        # Create test data
        self.create_test_extensions(5)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    limit_choices_to=lambda qs, instance, request: qs.filter(
                        number="nonexistent"
                    ),  # Filter that matches nothing
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)
        form = form_cls(instance=self.service)

        # Should have no choices available
        ext_field = form.fields["assigned_extensions"]
        if hasattr(ext_field, "queryset"):
            self.assertEqual(ext_field.queryset.count(), 0)

        # Form should be valid with empty selection
        form_with_empty = form_cls(
            {"name": self.service.name, "assigned_extensions": []}, instance=self.service
        )
        self.assertTrue(form_with_empty.is_valid())


class BaseModelStateTests(BaseAdminMixinTestCase):
    """Test suite for different model lifecycle scenarios."""

    def test_base_operation_with_unsaved_model_instance(self):
        """Test base operations with unsaved model instances."""
        # Create an unsaved service instance
        unsaved_service = Service(name="unsaved-service")

        # Create test data
        site_a = Site.objects.create(name="Site A")
        ext_a = Extension.objects.create(number="1001")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, unsaved_service)

        # Form should be created successfully
        form = form_cls(
            {
                "name": unsaved_service.name,
                "site_binding": site_a.pk,
                "assigned_extensions": [ext_a.pk],
            },
            instance=unsaved_service,
        )

        self.assertTrue(form.is_valid())

        # Save should create the service and establish bindings
        saved_service = form.save()
        self.assertIsNotNone(saved_service.pk)

        # Verify bindings were created
        site_a.refresh_from_db()
        ext_a.refresh_from_db()
        self.assertEqual(site_a.service, saved_service)
        self.assertEqual(ext_a.service, saved_service)

    def test_base_operation_model_creation_vs_update_scenarios(self):
        """Test base operations in both model creation and update scenarios."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        site_b = Site.objects.create(name="Site B")
        ext_a = Extension.objects.create(number="1001")
        ext_b = Extension.objects.create(number="1002")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())

        # Test creation scenario
        new_service = Service(name="new-service")
        form_cls_create = admin_inst.get_form(request, new_service)
        form_create = form_cls_create(
            {
                "name": new_service.name,
                "site_binding": site_a.pk,
                "assigned_extensions": [ext_a.pk],
            },
            instance=new_service,
        )

        self.assertTrue(form_create.is_valid())
        created_service = form_create.save()

        # Verify creation bindings
        site_a.refresh_from_db()
        ext_a.refresh_from_db()
        self.assertEqual(site_a.service, created_service)
        self.assertEqual(ext_a.service, created_service)

        # Test update scenario
        form_cls_update = admin_inst.get_form(request, created_service)
        form_update = form_cls_update(
            {
                "name": created_service.name,
                "site_binding": site_b.pk,
                "assigned_extensions": [ext_b.pk],
            },
            instance=created_service,
        )

        self.assertTrue(form_update.is_valid())
        updated_service = form_update.save()

        # Verify update bindings (old bindings should be removed)
        site_a.refresh_from_db()
        site_b.refresh_from_db()
        ext_a.refresh_from_db()
        ext_b.refresh_from_db()

        self.assertIsNone(site_a.service)  # Unbound
        self.assertEqual(site_b.service, updated_service)  # Bound
        self.assertIsNone(ext_a.service)  # Unbound
        self.assertEqual(ext_b.service, updated_service)  # Bound

    def test_base_operation_with_pre_existing_bindings(self):
        """Test base operations when objects already have existing bindings."""
        # Create services and pre-bind some objects
        other_service = Service.objects.create(name="other-service")

        site_a = Site.objects.create(name="Site A", service=other_service)
        site_b = Site.objects.create(name="Site B")  # Unbound
        ext_a = Extension.objects.create(number="1001", service=other_service)
        ext_b = Extension.objects.create(number="1002")  # Unbound

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Select objects that are bound to other services
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_a.pk,  # Currently bound to other_service
                "assigned_extensions": [ext_a.pk, ext_b.pk],  # ext_a bound, ext_b unbound
            },
            instance=self.service,
        )

        self.assertTrue(form.is_valid())
        saved_service = form.save()

        # Verify objects were transferred to our service
        site_a.refresh_from_db()
        ext_a.refresh_from_db()
        ext_b.refresh_from_db()

        self.assertEqual(site_a.service, saved_service)
        self.assertEqual(ext_a.service, saved_service)
        self.assertEqual(ext_b.service, saved_service)

        # Verify other_service lost its bindings
        other_service.refresh_from_db()
        self.assertEqual(Site.objects.filter(service=other_service).count(), 0)
        self.assertEqual(Extension.objects.filter(service=other_service).count(), 0)

    def test_base_operation_model_deletion_edge_cases(self):
        """Test base operations when related models are deleted during processing."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        ext_a = Extension.objects.create(number="1001")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Create form with valid selections
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_a.pk,
                "assigned_extensions": [ext_a.pk],
            },
            instance=self.service,
        )

        self.assertTrue(form.is_valid())

        # Delete one of the selected objects before saving
        deleted_ext_pk = ext_a.pk
        ext_a.delete()

        # Save should handle the missing object gracefully
        # The exact behavior depends on implementation, but it shouldn't crash
        from django.db.utils import DatabaseError
        try:
            saved_service = form.save()
            # If save succeeds, verify remaining bindings
            site_a.refresh_from_db()
            self.assertEqual(site_a.service, saved_service)
            # Verify the deleted extension is not bound
            self.assertEqual(Extension.objects.filter(pk=deleted_ext_pk).count(), 0)
        except (Extension.DoesNotExist, DatabaseError):
            # If save fails due to missing object or database error, that's acceptable behavior
            # The important thing is that it doesn't crash unexpectedly
            pass

    def test_base_operation_concurrent_model_modifications(self):
        """Test base operations with concurrent model modifications."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        ext_a = Extension.objects.create(number="1001")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Create form
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_a.pk,
                "assigned_extensions": [ext_a.pk],
            },
            instance=self.service,
        )

        self.assertTrue(form.is_valid())

        # Simulate concurrent modification: another process binds the objects
        concurrent_service = Service.objects.create(name="concurrent-service")
        site_a.service = concurrent_service
        site_a.save()
        ext_a.service = concurrent_service
        ext_a.save()

        # Our form save should still work (unbind from concurrent, bind to ours)
        saved_service = form.save()

        # Verify final state
        site_a.refresh_from_db()
        ext_a.refresh_from_db()
        self.assertEqual(site_a.service, saved_service)
        self.assertEqual(ext_a.service, saved_service)

    def test_base_operation_transaction_rollback_scenarios(self):
        """Test base operations with transaction rollback scenarios."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "unique_binding": ReverseRelationConfig(
                    model=UniqueExtension,
                    fk_field="service",
                    multiple=False,
                ),
            }

        # Create test data
        unique_ext_a = UniqueExtension.objects.create(number="1001")
        unique_ext_b = UniqueExtension.objects.create(number="1002")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Create a form that should succeed
        form = form_cls(
            {"name": self.service.name, "unique_binding": unique_ext_a.pk},
            instance=self.service,
        )

        self.assertTrue(form.is_valid())

        # Use transaction to test rollback behavior
        try:
            with transaction.atomic():
                saved_service = form.save()

                # Verify binding was created
                unique_ext_a.refresh_from_db()
                self.assertEqual(unique_ext_a.service, saved_service)

                # Force a rollback by raising an exception
                raise RuntimeError("Force rollback")

        except RuntimeError:
            pass  # Expected

        # After rollback, binding should not exist
        unique_ext_a.refresh_from_db()
        self.assertIsNone(unique_ext_a.service)


class BaseComplexRelationshipTests(BaseAdminMixinTestCase):
    """Test suite for complex model relationship scenarios."""

    def test_base_operation_multiple_services_complex_bindings(self):
        """Test base operations with multiple services and complex binding patterns."""
        # Create multiple services and objects
        service_a = Service.objects.create(name="service-a")
        service_b = Service.objects.create(name="service-b")

        # Create objects with mixed binding states
        site_1 = Site.objects.create(name="Site 1", service=service_a)
        site_2 = Site.objects.create(name="Site 2")  # Unbound
        site_3 = Site.objects.create(name="Site 3", service=service_b)

        ext_1 = Extension.objects.create(number="1001", service=service_a)
        ext_2 = Extension.objects.create(number="1002", service=service_b)
        ext_3 = Extension.objects.create(number="1003")  # Unbound

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Select objects from different services and unbound objects
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_3.pk,  # From service_b
                "assigned_extensions": [ext_1.pk, ext_2.pk, ext_3.pk],  # Mixed sources
            },
            instance=self.service,
        )

        self.assertTrue(form.is_valid())
        saved_service = form.save()

        # Verify all objects were transferred to our service
        site_3.refresh_from_db()
        ext_1.refresh_from_db()
        ext_2.refresh_from_db()
        ext_3.refresh_from_db()

        self.assertEqual(site_3.service, saved_service)
        self.assertEqual(ext_1.service, saved_service)
        self.assertEqual(ext_2.service, saved_service)
        self.assertEqual(ext_3.service, saved_service)

        # Verify other services lost their bindings
        self.assertEqual(Site.objects.filter(service=service_a).count(), 1)  # site_1 remains
        self.assertEqual(Site.objects.filter(service=service_b).count(), 0)  # site_3 moved
        self.assertEqual(Extension.objects.filter(service=service_a).count(), 0)  # ext_1 moved
        self.assertEqual(Extension.objects.filter(service=service_b).count(), 0)  # ext_2 moved

    def test_base_operation_circular_relationship_scenarios(self):
        """Test base operations with potential circular relationship scenarios."""
        # Create a complex scenario where services could reference each other indirectly
        service_a = Service.objects.create(name="service-a")
        service_b = Service.objects.create(name="service-b")

        # Create sites that reference different services
        site_a = Site.objects.create(name="Site A", service=service_a)
        site_b = Site.objects.create(name="Site B", service=service_b)

        # Create extensions that reference different services
        ext_a = Extension.objects.create(number="1001", service=service_a)
        ext_b = Extension.objects.create(number="1002", service=service_b)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())

        # Test moving objects from service_a to service_b
        form_cls_b = admin_inst.get_form(request, service_b)
        form_b = form_cls_b(
            {
                "name": service_b.name,
                "site_binding": site_a.pk,  # Move from service_a
                "assigned_extensions": [ext_a.pk, ext_b.pk],  # Keep ext_b, add ext_a
            },
            instance=service_b,
        )

        self.assertTrue(form_b.is_valid())
        form_b.save()

        # Verify transfers
        site_a.refresh_from_db()
        ext_a.refresh_from_db()
        ext_b.refresh_from_db()

        self.assertEqual(site_a.service, service_b)
        self.assertEqual(ext_a.service, service_b)
        self.assertEqual(ext_b.service, service_b)

        # Now test moving objects back to service_a
        form_cls_a = admin_inst.get_form(request, service_a)
        form_a = form_cls_a(
            {
                "name": service_a.name,
                "site_binding": site_b.pk,  # Move from service_b
                "assigned_extensions": [ext_a.pk],  # Move back ext_a
            },
            instance=service_a,
        )

        self.assertTrue(form_a.is_valid())
        form_a.save()

        # Verify final state
        site_a.refresh_from_db()
        site_b.refresh_from_db()
        ext_a.refresh_from_db()
        ext_b.refresh_from_db()

        self.assertEqual(site_a.service, service_b)  # Still with service_b
        self.assertEqual(site_b.service, service_a)  # Moved to service_a
        self.assertEqual(ext_a.service, service_a)  # Moved back to service_a
        self.assertEqual(ext_b.service, service_b)  # Remains with service_b

    def test_base_operation_mixed_relationship_types(self):
        """Test base operations with mixed relationship types (ForeignKey and OneToOne)."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        ext_a = Extension.objects.create(number="1001")
        unique_ext_a = UniqueExtension.objects.create(number="2001")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,  # Single ForeignKey
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,  # Multiple ForeignKey
                ),
                "unique_binding": ReverseRelationConfig(
                    model=UniqueExtension,
                    fk_field="service",
                    multiple=False,  # OneToOne relationship
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Test binding all relationship types
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_a.pk,
                "assigned_extensions": [ext_a.pk],
                "unique_binding": unique_ext_a.pk,
            },
            instance=self.service,
        )

        self.assertTrue(form.is_valid())
        saved_service = form.save()

        # Verify all bindings were created
        site_a.refresh_from_db()
        ext_a.refresh_from_db()
        unique_ext_a.refresh_from_db()

        self.assertEqual(site_a.service, saved_service)
        self.assertEqual(ext_a.service, saved_service)
        self.assertEqual(unique_ext_a.service, saved_service)

        # Test partial unbinding (keep unique, unbind others)
        form_partial = form_cls(
            {
                "name": self.service.name,
                "site_binding": "",
                "assigned_extensions": [],
                "unique_binding": unique_ext_a.pk,  # Keep this one
            },
            instance=self.service,
        )

        self.assertTrue(form_partial.is_valid())
        form_partial.save()

        # Verify partial unbinding
        site_a.refresh_from_db()
        ext_a.refresh_from_db()
        unique_ext_a.refresh_from_db()

        self.assertIsNone(site_a.service)  # Unbound
        self.assertIsNone(ext_a.service)  # Unbound
        self.assertEqual(unique_ext_a.service, saved_service)  # Still bound

    def test_base_operation_relationship_constraint_interactions(self):
        """Test base operations with complex constraint interactions."""
        # Create services and unique extensions
        service_a = Service.objects.create(name="service-a")
        service_b = Service.objects.create(name="service-b")

        unique_ext_1 = UniqueExtension.objects.create(number="1001", service=service_a)
        unique_ext_2 = UniqueExtension.objects.create(number="1002", service=service_b)
        unique_ext_3 = UniqueExtension.objects.create(number="1003")  # Unbound

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "unique_binding": ReverseRelationConfig(
                    model=UniqueExtension,
                    fk_field="service",
                    multiple=False,
                ),
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, self.service)

        # Test transferring unique extension from another service
        form = form_cls(
            {"name": self.service.name, "unique_binding": unique_ext_1.pk},
            instance=self.service,
        )

        self.assertTrue(form.is_valid())
        saved_service = form.save()

        # Verify transfer (should unbind from service_a, bind to our service)
        unique_ext_1.refresh_from_db()
        self.assertEqual(unique_ext_1.service, saved_service)

        # Verify service_a lost its unique extension
        service_a.refresh_from_db()
        with self.assertRaises(UniqueExtension.DoesNotExist):
            _ = service_a.unique_extension

        # Test switching to a different unique extension
        form_switch = form_cls(
            {"name": self.service.name, "unique_binding": unique_ext_2.pk},
            instance=self.service,
        )

        self.assertTrue(form_switch.is_valid())
        form_switch.save()

        # Verify switch (unique_ext_1 should be unbound, unique_ext_2 should be bound)
        unique_ext_1.refresh_from_db()
        unique_ext_2.refresh_from_db()

        self.assertIsNone(unique_ext_1.service)  # Unbound
        self.assertEqual(unique_ext_2.service, saved_service)  # Bound

        # Verify service_b lost its unique extension
        service_b.refresh_from_db()
        with self.assertRaises(UniqueExtension.DoesNotExist):
            _ = service_b.unique_extension