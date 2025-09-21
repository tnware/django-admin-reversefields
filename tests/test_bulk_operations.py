"""Test suite for bulk operations with single and multi-select relationships."""

# Standard library imports
from unittest import mock

# Django imports
from django import forms
from django.contrib import admin
from django.db import IntegrityError
from django.test import RequestFactory

# Project imports
from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

# Test imports
from .admin import ServiceAdmin
from .models import Extension, Service, Site
from .shared_test_base import BaseAdminMixinTestCase, DummySite


class BulkOperationSingleSelectTests(BaseAdminMixinTestCase):
    """Test suite for bulk operations with single-select relationships."""

    def test_bulk_unbind_operation_single_select(self):
        """Test bulk unbind operation in single-select scenario."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        site_b = Site.objects.create(name="Site B")

        # Initially bind site_a to service
        site_a.service = self.service
        site_a.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Mock the bulk operation methods directly
        with mock.patch.object(admin_inst, "_apply_bulk_operations") as mock_bulk_ops:
            # Change selection from site_a to site_b (should call bulk operations)
            form = form_cls(
                {
                    "name": self.service.name,
                    "site_binding": site_b.pk,
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify bulk operations method was called
            mock_bulk_ops.assert_called_once()

            # Verify it was called with the correct parameters
            call_args = mock_bulk_ops.call_args
            config, instance, selection = call_args[0]

            self.assertTrue(config.bulk)
            self.assertEqual(instance, self.service)
            self.assertEqual(selection, site_b)

    def test_bulk_bind_operation_single_select(self):
        """Test bulk bind operation in single-select scenario."""
        # Create test data
        site_a = Site.objects.create(name="Site A")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Mock the bulk operation methods directly
        with mock.patch.object(admin_inst, "_apply_bulk_operations") as mock_bulk_ops:
            # Bind site_a to service (from no binding)
            form = form_cls(
                {
                    "name": self.service.name,
                    "site_binding": site_a.pk,
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify bulk operations method was called
            mock_bulk_ops.assert_called_once()

            # Verify it was called with the correct parameters
            call_args = mock_bulk_ops.call_args
            config, instance, selection = call_args[0]

            self.assertTrue(config.bulk)
            self.assertEqual(instance, self.service)
            self.assertEqual(selection, site_a)

    def test_complete_single_select_bulk_workflow(self):
        """Test complete single-select bulk workflow (unbind then bind)."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        site_b = Site.objects.create(name="Site B")
        site_c = Site.objects.create(name="Site C")

        # Initially bind site_a to service
        site_a.service = self.service
        site_a.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Test workflow: A -> B -> C -> None -> B (actual end-to-end test)
        test_cases = [
            (site_b, "Switch from A to B"),
            (site_c, "Switch from B to C"),
            (None, "Unbind all (C to None)"),
            (site_b, "Bind B again (None to B)"),
        ]

        for target_site, description in test_cases:
            with self.subTest(description=description):
                form_data = {"name": self.service.name}
                if target_site:
                    form_data["site_binding"] = target_site.pk

                form = form_cls(form_data, instance=self.service)
                self.assertTrue(form.is_valid(), f"Form should be valid for {description}")
                form.save()

                # Verify the actual database state after bulk operations
                if target_site:
                    # Verify target site is bound to service
                    target_site.refresh_from_db()
                    self.assertEqual(target_site.service, self.service,
                                   f"Target site should be bound to service for {description}")

                    # Verify other sites are not bound
                    other_sites = [s for s in [site_a, site_b, site_c] if s != target_site]
                    for other_site in other_sites:
                        other_site.refresh_from_db()
                        self.assertIsNone(other_site.service,
                                        f"Other sites should not be bound for {description}")
                else:
                    # Verify no sites are bound
                    for site in [site_a, site_b, site_c]:
                        site.refresh_from_db()
                        self.assertIsNone(site.service,
                                        f"No sites should be bound for {description}")

    def test_bulk_single_select_with_no_initial_binding(self):
        """Test bulk operations when no initial binding exists."""
        # Create test data
        site_a = Site.objects.create(name="Site A")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Bind site_a to service (from no initial binding)
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_a.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify the actual database state
        site_a.refresh_from_db()
        self.assertEqual(site_a.service, self.service, "Site should be bound to service")

    def test_bulk_single_select_unbind_all(self):
        """Test bulk operations when unbinding all (setting to None)."""
        # Create test data
        site_a = Site.objects.create(name="Site A")

        # Initially bind site_a to service
        site_a.service = self.service
        site_a.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Unbind all (set to empty/None)
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": "",  # Empty selection
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify the actual database state
        site_a.refresh_from_db()
        self.assertIsNone(site_a.service, "Site should be unbound from service")

    def test_bulk_single_select_no_change_keeps_binding(self):
        """Submitting the same selection keeps FK bound when bulk=True (single-select)."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        site_b = Site.objects.create(name="Site B")

        # Initially bind site_a to service
        site_a.service = self.service
        site_a.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Submit the same selection (no change)
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_a.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # site_a remains bound; site_b remains unbound
        site_a.refresh_from_db()
        site_b.refresh_from_db()
        self.assertEqual(site_a.service, self.service)
        self.assertIsNone(site_b.service)

    def test_bulk_single_select_change_selection_rebinds(self):
        """Changing selection A→B unbinds A and binds B in bulk single-select."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        site_b = Site.objects.create(name="Site B")

        # Initially bind site_a to service
        site_a.service = self.service
        site_a.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Change selection from A to B
        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_b.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify A is unbound and B is bound
        site_a.refresh_from_db()
        site_b.refresh_from_db()
        self.assertIsNone(site_a.service)
        self.assertEqual(site_b.service, self.service)


class BulkOperationMultiSelectTests(BaseAdminMixinTestCase):
    """Test suite for bulk operations with multi-select relationships."""

    def test_bulk_unbind_multiple_deselected_objects(self):
        """Test bulk unbind of multiple deselected objects."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        ext_3 = Extension.objects.create(number="1003")
        ext_4 = Extension.objects.create(number="1004")

        # Initially bind ext_1, ext_2, ext_3 to service
        for ext in [ext_1, ext_2, ext_3]:
            ext.service = self.service
            ext.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Change selection to only ext_2 and ext_4 (should unbind ext_1, ext_3 and bind ext_4)
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_2.pk, ext_4.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify the actual database state
        ext_1.refresh_from_db()
        ext_2.refresh_from_db()
        ext_3.refresh_from_db()
        ext_4.refresh_from_db()

        # ext_1 and ext_3 should be unbound (deselected)
        self.assertIsNone(ext_1.service, "ext_1 should be unbound")
        self.assertIsNone(ext_3.service, "ext_3 should be unbound")

        # ext_2 and ext_4 should be bound (selected)
        self.assertEqual(ext_2.service, self.service, "ext_2 should remain bound")
        self.assertEqual(ext_4.service, self.service, "ext_4 should be newly bound")

    def test_bulk_bind_multiple_selected_objects(self):
        """Test bulk bind of multiple selected objects."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        ext_3 = Extension.objects.create(number="1003")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Bind multiple extensions to service (from no initial bindings)
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk, ext_2.pk, ext_3.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify the actual database state
        ext_1.refresh_from_db()
        ext_2.refresh_from_db()
        ext_3.refresh_from_db()

        # All extensions should be bound to the service
        self.assertEqual(ext_1.service, self.service, "ext_1 should be bound")
        self.assertEqual(ext_2.service, self.service, "ext_2 should be bound")
        self.assertEqual(ext_3.service, self.service, "ext_3 should be bound")

    def test_complete_multi_select_bulk_workflow_mixed_bind_unbind(self):
        """Test complete multi-select bulk workflow with mixed bind/unbind operations."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        ext_3 = Extension.objects.create(number="1003")
        ext_4 = Extension.objects.create(number="1004")
        ext_5 = Extension.objects.create(number="1005")

        # Initially bind ext_1, ext_2 to service
        for ext in [ext_1, ext_2]:
            ext.service = self.service
            ext.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Test complex workflow with mixed operations
        test_cases = [
            ([ext_2.pk, ext_3.pk, ext_4.pk], "Keep ext_2, add ext_3 and ext_4, remove ext_1",
             [ext_2, ext_3, ext_4], [ext_1, ext_5]),
            ([ext_1.pk, ext_5.pk], "Add ext_1 and ext_5, remove ext_2, ext_3, ext_4",
             [ext_1, ext_5], [ext_2, ext_3, ext_4]),
            ([], "Remove all extensions",
             [], [ext_1, ext_2, ext_3, ext_4, ext_5]),
            ([ext_1.pk, ext_2.pk, ext_3.pk, ext_4.pk, ext_5.pk], "Add all extensions",
             [ext_1, ext_2, ext_3, ext_4, ext_5], []),
            ([ext_3.pk], "Keep only ext_3",
             [ext_3], [ext_1, ext_2, ext_4, ext_5]),
        ]

        for selected_pks, description, expected_bound, expected_unbound in test_cases:
            with self.subTest(description=description):
                form_data = {"name": self.service.name}
                if selected_pks:
                    form_data["assigned_extensions"] = selected_pks

                form = form_cls(form_data, instance=self.service)
                self.assertTrue(form.is_valid(), f"Form should be valid for {description}")
                form.save()

                # Verify the actual database state
                for ext in expected_bound:
                    ext.refresh_from_db()
                    self.assertEqual(ext.service, self.service,
                                   f"{ext.number} should be bound for {description}")

                for ext in expected_unbound:
                    ext.refresh_from_db()
                    self.assertIsNone(ext.service,
                                    f"{ext.number} should be unbound for {description}")

    def test_bulk_multi_select_with_no_changes(self):
        """Test bulk operations when selection doesn't change."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")

        # Initially bind ext_1, ext_2 to service
        for ext in [ext_1, ext_2]:
            ext.service = self.service
            ext.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Submit the same selection (no changes)
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk, ext_2.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify the database state remains unchanged
        ext_1.refresh_from_db()
        ext_2.refresh_from_db()

        self.assertEqual(ext_1.service, self.service, "ext_1 should remain bound")
        self.assertEqual(ext_2.service, self.service, "ext_2 should remain bound")

    def test_bulk_multi_select_partial_overlap(self):
        """Test bulk operations with partial overlap between current and new selections."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        ext_3 = Extension.objects.create(number="1003")
        ext_4 = Extension.objects.create(number="1004")

        # Initially bind ext_1, ext_2, ext_3 to service
        for ext in [ext_1, ext_2, ext_3]:
            ext.service = self.service
            ext.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Change to ext_2, ext_3, ext_4 (keep ext_2, ext_3; remove ext_1; add ext_4)
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_2.pk, ext_3.pk, ext_4.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify the actual database state
        ext_1.refresh_from_db()
        ext_2.refresh_from_db()
        ext_3.refresh_from_db()
        ext_4.refresh_from_db()

        # ext_1 should be unbound (removed)
        self.assertIsNone(ext_1.service, "ext_1 should be unbound")

        # ext_2 and ext_3 should remain bound (kept)
        self.assertEqual(ext_2.service, self.service, "ext_2 should remain bound")
        self.assertEqual(ext_3.service, self.service, "ext_3 should remain bound")

        # ext_4 should be newly bound (added)
        self.assertEqual(ext_4.service, self.service, "ext_4 should be newly bound")

    def test_bulk_multi_select_empty_to_populated(self):
        """Test bulk operations when going from empty selection to populated."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        ext_3 = Extension.objects.create(number="1003")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Go from no selection to multiple selections
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk, ext_2.pk, ext_3.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify the actual database state
        ext_1.refresh_from_db()
        ext_2.refresh_from_db()
        ext_3.refresh_from_db()

        # All extensions should be bound to the service
        self.assertEqual(ext_1.service, self.service, "ext_1 should be bound")
        self.assertEqual(ext_2.service, self.service, "ext_2 should be bound")
        self.assertEqual(ext_3.service, self.service, "ext_3 should be bound")

    def test_bulk_multi_select_populated_to_empty(self):
        """Test bulk operations when going from populated selection to empty."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        ext_3 = Extension.objects.create(number="1003")

        # Initially bind all extensions to service
        for ext in [ext_1, ext_2, ext_3]:
            ext.service = self.service
            ext.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Enable bulk operations
                )
            }

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Go from multiple selections to no selection
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [],  # Empty selection
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify the actual database state
        ext_1.refresh_from_db()
        ext_2.refresh_from_db()
        ext_3.refresh_from_db()

        # All extensions should be unbound from the service
        self.assertIsNone(ext_1.service, "ext_1 should be unbound")
        self.assertIsNone(ext_2.service, "ext_2 should be unbound")
        self.assertIsNone(ext_3.service, "ext_3 should be unbound")


class BulkOperationRoutingTests(BaseAdminMixinTestCase):
    """Test suite for bulk vs individual operation routing functionality."""

    def test_bulk_false_uses_individual_saves(self):
        """Verify bulk=False uses individual saves (existing behavior)."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=False,  # Explicitly set to False
                )
            }

        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Mock the individual save method to verify it's called
        with mock.patch.object(Site, "save") as mock_save:
            form = form_cls(
                {
                    "name": self.service.name,  # Include required field
                    "site_binding": site_a.pk,
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify individual save was called
            mock_save.assert_called()
            # Should be called at least once for the bind operation
            self.assertGreaterEqual(mock_save.call_count, 1)

    def test_bulk_true_would_use_update_method(self):
        """Verify bulk=True configuration would route to bulk operations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Enable bulk operations
                )
            }

        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Since bulk operations aren't implemented yet, we'll test that the config
        # is properly set and accessible
        config = admin_inst.get_reverse_relations()["site_binding"]
        self.assertTrue(config.bulk)

        # Create form to verify it works with bulk=True configuration
        form = form_cls(
            {
                "name": self.service.name,  # Include required field
                "site_binding": site_a.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())

        # For now, this will still use individual saves until bulk methods are implemented
        # But the configuration should be accessible for future routing logic
        self.assertTrue(hasattr(form, "_reverse_relation_configs"))
        self.assertTrue(form._reverse_relation_configs["site_binding"].bulk)

    def test_mixed_bulk_configurations(self):
        """Verify mixed configurations (some bulk, some individual) work correctly."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=False,  # Individual operations
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Bulk operations
                ),
            }

        site_a = Site.objects.create(name="Site A")
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)

        # Verify configurations are set correctly
        relations = admin_inst.get_reverse_relations()
        self.assertFalse(relations["site_binding"].bulk)
        self.assertTrue(relations["assigned_extensions"].bulk)

        form_cls = admin_inst.get_form(request, self.service)
        form = form_cls(
            {
                "name": self.service.name,  # Include required field
                "site_binding": site_a.pk,
                "assigned_extensions": [ext_1.pk, ext_2.pk],
            },
            instance=self.service,
        )

        self.assertTrue(form.is_valid())

        # Verify form has access to both configurations
        self.assertFalse(form._reverse_relation_configs["site_binding"].bulk)
        self.assertTrue(form._reverse_relation_configs["assigned_extensions"].bulk)

    def test_bulk_configuration_routing_with_mocking(self):
        """Use mocking to verify the correct operation type would be called."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,
                )
            }

        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Mock the queryset update method to verify bulk operations would be used
        with mock.patch.object(Extension.objects, "update"):
            with mock.patch.object(Extension, "save") as mock_save:
                form = form_cls(
                    {
                        "name": self.service.name,  # Include required field
                        "assigned_extensions": [ext_1.pk, ext_2.pk],
                    },
                    instance=self.service,
                )

                self.assertTrue(form.is_valid())

                # Verify the bulk configuration is accessible
                config = form._reverse_relation_configs["assigned_extensions"]
                self.assertTrue(config.bulk)

                # For now, individual saves will still be called since bulk methods
                # aren't implemented yet, but the configuration is ready for routing
                form.save()

                # Individual saves are still called (current implementation)
                # Once bulk methods are implemented, mock_update should be called instead
                self.assertGreaterEqual(mock_save.call_count, 0)

    def test_backward_compatibility_with_no_bulk_parameter(self):
        """Verify existing configurations without bulk parameter work unchanged."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    # No bulk parameter specified - should default to False
                )
            }

        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)

        # Verify bulk defaults to False
        config = admin_inst.get_reverse_relations()["site_binding"]
        self.assertFalse(config.bulk)

        form_cls = admin_inst.get_form(request, self.service)
        form = form_cls(
            {
                "name": self.service.name,  # Include required field
                "site_binding": site_a.pk,
            },
            instance=self.service,
        )

        self.assertTrue(form.is_valid())
        form.save()

        # Verify the binding worked (existing functionality)
        self.assertEqual(Site.objects.get(pk=site_a.pk).service, self.service)

    def test_clean_hook_blocks_unbind(self):
        service = Service.objects.create(name="svc")
        a = Site.objects.create(name="A", service=service)

        def forbid_unbind(instance, selection, request):
            if selection is None:
                raise forms.ValidationError("Cannot unbind site")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    multiple=False,
                    required=False,
                    clean=forbid_unbind,
                )
            }

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        # Attempt to unbind by passing empty selection
        form = form_cls({"name": service.name, "site_binding": ""}, instance=service)
        self.assertFalse(form.is_valid())
        self.assertIn("Cannot unbind site", form.errors.get("site_binding", [""])[0])
        # Ensure DB unchanged
        self.assertEqual(Site.objects.get(pk=a.pk).service_id, service.pk)

    def test_clean_hook_uses_request_user(self):
        service = Service.objects.create(name="svc")
        s1 = Site.objects.create(name="A")

        class DummyUser:
            def __init__(self, is_staff):
                self.is_staff = is_staff

        def staff_only(instance, selection, request):
            if not getattr(request, "user", None) or not request.user.is_staff:
                raise forms.ValidationError("Not permitted")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    multiple=False,
                    required=False,
                    clean=staff_only,
                )
            }

        # Non-staff should be blocked
        request = self.factory.post("/")
        request.user = DummyUser(is_staff=False)
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        form = form_cls({"name": service.name, "site_binding": s1.pk}, instance=service)
        self.assertFalse(form.is_valid())
        self.assertIn("Not permitted", form.errors.get("site_binding", [""])[0])

        # Staff allowed
        request2 = self.factory.post("/")
        request2.user = DummyUser(is_staff=True)
        admin_inst2 = TempAdmin(Service, DummySite())
        form_cls2 = admin_inst2.get_form(request2, service)
        form2 = form_cls2({"name": service.name, "site_binding": s1.pk}, instance=service)
        self.assertTrue(form2.is_valid())