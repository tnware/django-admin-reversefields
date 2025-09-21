"""Test suite for bulk configuration parameter functionality."""

# Standard library imports
from unittest import mock

# Django imports
from django.contrib import admin

# Project imports
from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

# Test imports
from .models import Extension, Service, Site
from .shared_test_base import BaseAdminMixinTestCase


class BulkConfigurationTests(BaseAdminMixinTestCase):
    """Test suite for bulk configuration parameter functionality."""

    def test_bulk_parameter_defaults_to_false(self):
        """Verify bulk parameter defaults to False for backward compatibility."""
        config = ReverseRelationConfig(
            model=Site,
            fk_field="service",
        )
        self.assertFalse(config.bulk)

    def test_bulk_parameter_can_be_set_to_true(self):
        """Verify bulk=True can be configured explicitly."""
        config = ReverseRelationConfig(
            model=Site,
            fk_field="service",
            bulk=True,
        )
        self.assertTrue(config.bulk)

    def test_bulk_parameter_can_be_set_to_false_explicitly(self):
        """Verify bulk=False can be configured explicitly."""
        config = ReverseRelationConfig(
            model=Site,
            fk_field="service",
            bulk=False,
        )
        self.assertFalse(config.bulk)

    def test_bulk_configuration_is_stored_and_accessible(self):
        """Verify bulk configuration is properly stored and accessible."""
        # Test with bulk=True
        config_bulk_true = ReverseRelationConfig(
            model=Site,
            fk_field="service",
            multiple=True,
            bulk=True,
        )
        self.assertTrue(config_bulk_true.bulk)
        self.assertEqual(config_bulk_true.model, Site)
        self.assertEqual(config_bulk_true.fk_field, "service")
        self.assertTrue(config_bulk_true.multiple)

        # Test with bulk=False
        config_bulk_false = ReverseRelationConfig(
            model=Extension,
            fk_field="service",
            multiple=False,
            bulk=False,
        )
        self.assertFalse(config_bulk_false.bulk)
        self.assertEqual(config_bulk_false.model, Extension)
        self.assertEqual(config_bulk_false.fk_field, "service")
        self.assertFalse(config_bulk_false.multiple)

    def test_bulk_configuration_with_other_parameters(self):
        """Verify bulk parameter works correctly with other configuration parameters."""
        config = ReverseRelationConfig(
            model=Site,
            fk_field="service",
            label="Test Sites",
            help_text="Select sites for this service",
            required=True,
            multiple=True,
            bulk=True,
        )

        self.assertTrue(config.bulk)
        self.assertEqual(config.label, "Test Sites")
        self.assertEqual(config.help_text, "Select sites for this service")
        self.assertTrue(config.required)
        self.assertTrue(config.multiple)

    def test_bulk_configuration_immutability(self):
        """Verify bulk configuration is immutable (frozen dataclass)."""
        config = ReverseRelationConfig(
            model=Site,
            fk_field="service",
            bulk=True,
        )

        # Attempt to modify bulk parameter should raise AttributeError
        with self.assertRaises(AttributeError):
            config.bulk = False


class BulkOperationBackwardCompatibilityTests(BaseAdminMixinTestCase):
    """Test suite for backward compatibility with bulk operations."""

    def test_existing_configurations_without_bulk_parameter_work_unchanged(self):
        """Test that existing configurations without bulk parameter work unchanged."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    # No bulk parameter specified - should default to False
                ),
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    # No bulk parameter specified - should default to False
                )
            }

        # Verify that bulk defaults to False
        config = TestAdmin.reverse_relations["assigned_extensions"]
        self.assertFalse(config.bulk, "bulk should default to False for backward compatibility")

        config = TestAdmin.reverse_relations["site_binding"]
        self.assertFalse(config.bulk, "bulk should default to False for backward compatibility")

        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Mock individual save operations to verify they are used instead of bulk
        with mock.patch.object(Extension, 'save') as mock_ext_save:
            with mock.patch.object(Site, 'save') as mock_site_save:
                form = form_cls(
                    {
                        "name": self.service.name,
                        "assigned_extensions": [ext_1.pk, ext_2.pk],
                        "site_binding": site_a.pk,
                    },
                    instance=self.service,
                )
                self.assertTrue(form.is_valid())
                form.save()

                # Verify that individual save methods were called (not bulk operations)
                self.assertGreater(mock_ext_save.call_count, 0,
                                 "Individual Extension.save() should be called when bulk=False")
                self.assertGreater(mock_site_save.call_count, 0,
                                 "Individual Site.save() should be called when bulk=False")

    def test_mixed_configurations_bulk_and_individual_work_correctly(self):
        """Test that mixed configurations (some bulk, some individual) work correctly."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Use bulk operations
                ),
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=False,  # Use individual operations
                )
            }

        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk, ext_2.pk],
                "site_binding": site_a.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify that both operations worked correctly
        # Extensions should be bound (bulk operation)
        bound_extensions = Extension.objects.filter(service=self.service)
        self.assertEqual(bound_extensions.count(), 2)
        self.assertIn(ext_1, bound_extensions)
        self.assertIn(ext_2, bound_extensions)

        # Site should be bound (individual operation)
        self.assertEqual(Site.objects.get(pk=site_a.pk).service, self.service)

    def test_bulk_parameter_explicit_false_uses_individual_operations(self):
        """Test that explicitly setting bulk=False uses individual operations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=False,  # Explicitly set to False
                )
            }

        ext_1 = Extension.objects.create(number="1001")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Mock individual save operations to verify they are used
        with mock.patch.object(Extension, 'save') as mock_save:
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk],
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that individual save was called
            mock_save.assert_called()

    def test_bulk_parameter_explicit_true_uses_bulk_operations(self):
        """Test that explicitly setting bulk=True uses bulk operations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,  # Explicitly set to True
                )
            }

        ext_1 = Extension.objects.create(number="1001")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        
        # Mock bulk operations method to verify it's called
        with mock.patch.object(admin_inst, '_apply_bulk_operations') as mock_bulk_ops:
            form.save()
            
            # Verify that bulk operations were used
            mock_bulk_ops.assert_called()

    def test_all_existing_functionality_remains_intact(self):
        """Test that all existing functionality remains intact with bulk feature."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    label="Test Extensions",
                    help_text="Select extensions",
                    required=False,
                    # No bulk parameter - should use individual operations
                )
            }

        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Test form field properties are preserved
        form = form_cls(instance=self.service)
        field = form.fields["assigned_extensions"]

        self.assertEqual(field.label, "Test Extensions")
        self.assertEqual(field.help_text, "Select extensions")
        self.assertFalse(field.required)

        # Test that operations work correctly
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk, ext_2.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify that extensions were bound correctly
        bound_extensions = Extension.objects.filter(service=self.service)
        self.assertEqual(bound_extensions.count(), 2)
        self.assertIn(ext_1, bound_extensions)
        self.assertIn(ext_2, bound_extensions)

        # Test unbinding works
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk],  # Only ext_1, should unbind ext_2
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify that ext_2 was unbound
        bound_extensions = Extension.objects.filter(service=self.service)
        self.assertEqual(bound_extensions.count(), 1)
        self.assertEqual(bound_extensions.first(), ext_1)
        self.assertIsNone(Extension.objects.get(pk=ext_2.pk).service)