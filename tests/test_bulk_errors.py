"""Test suite for bulk operation error scenarios and edge cases."""

# Standard library imports
from unittest import mock

# Django imports
from django import forms
from django.contrib import admin
from django.db import IntegrityError

# Project imports
from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

# Test imports
from .models import Extension, Service, Site, UniqueExtension
from .shared_test_base import BaseAdminMixinTestCase


class BulkOperationErrorTests(BaseAdminMixinTestCase):
    """Test suite for bulk operation error scenarios and edge cases."""

    def test_bulk_database_integrity_error_single_select(self):
        """Test database integrity errors during bulk operations for single-select."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "unique_binding": ReverseRelationConfig(
                    model=UniqueExtension,
                    fk_field="service",
                    multiple=False,
                    bulk=True,
                )
            }

        # Create a UniqueExtension that will cause constraint violation
        UniqueExtension.objects.create(number="1001", service=self.service)
        target = UniqueExtension.objects.create(number="1002")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        form = form_cls(
            {
                "name": self.service.name,
                "unique_binding": target.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())

        # Mock the queryset update method to simulate an IntegrityError during save
        with mock.patch.object(UniqueExtension._default_manager, 'filter') as mock_filter:
            mock_queryset = mock.Mock()
            mock_queryset.exists.return_value = True
            mock_queryset.update.side_effect = IntegrityError("Constraint violation")
            mock_filter.return_value = mock_queryset

            # Should raise ValidationError with meaningful message
            with self.assertRaises(forms.ValidationError) as cm:
                form.save()

            error_message = str(cm.exception)
            self.assertIn("Bulk", error_message)
            self.assertIn("operation failed", error_message)
            self.assertIn("unique extension", error_message)  # Model verbose name is lowercase
            self.assertIn("Constraint violation", error_message)

    def test_bulk_database_integrity_error_multi_select(self):
        """Test database integrity errors during bulk operations for multi-select."""

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

        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk, ext_2.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())

        # Mock the queryset filter and update methods to simulate an IntegrityError
        # during bind operation
        with mock.patch.object(Extension._default_manager, 'filter') as mock_filter:
            mock_queryset = mock.Mock()
            mock_queryset.update.side_effect = IntegrityError("Foreign key constraint failed")
            mock_filter.return_value = mock_queryset

            # Should raise ValidationError with meaningful message
            with self.assertRaises(forms.ValidationError) as cm:
                form.save()

            error_message = str(cm.exception)
            self.assertIn("Bulk", error_message)
            self.assertIn("operation failed", error_message)
            self.assertIn("extension", error_message)  # Model verbose name is lowercase
            self.assertIn("Foreign key constraint failed", error_message)



    def test_bulk_unexpected_error_provides_meaningful_message(self):
        """Test that unexpected errors during bulk operations provide meaningful messages."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,
                )
            }

        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        form = form_cls(
            {
                "name": self.service.name,
                "site_binding": site_a.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())

        # Mock the queryset filter and update methods to simulate an unexpected error
        with mock.patch.object(Site._default_manager, 'filter') as mock_filter:
            mock_queryset = mock.Mock()
            mock_queryset.exists.return_value = True
            mock_queryset.update.side_effect = RuntimeError("Unexpected database error")
            mock_filter.return_value = mock_queryset

            # Should raise ValidationError with meaningful message
            with self.assertRaises(forms.ValidationError) as cm:
                form.save()

            error_message = str(cm.exception)
            # The error message format depends on which operation fails first
            self.assertTrue(
                "Bulk operation failed" in error_message or
                "Unexpected error during bulk" in error_message
            )
            self.assertIn("Unexpected database error", error_message)

    def test_bulk_unbind_error_provides_specific_message(self):
        """Test that unbind operation errors provide specific error messages."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,
                )
            }

        # Create existing extensions bound to the service
        Extension.objects.create(number="1001", service=self.service)
        Extension.objects.create(number="1002", service=self.service)
        ext_3 = Extension.objects.create(number="1003")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Mock the _apply_bulk_unbind method to simulate an error during unbind
        with mock.patch.object(
            admin_inst,
            '_apply_bulk_unbind',
            side_effect=IntegrityError("Cannot unbind due to constraint"),
        ):
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_3.pk],  # Only select ext_3
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())

            # Should raise ValidationError from the unbind operation
            with self.assertRaises(forms.ValidationError) as cm:
                form.save()

            error_message = str(cm.exception)
            self.assertIn("Cannot unbind due to constraint", error_message)

    def test_bulk_bind_error_provides_specific_message(self):
        """Test that bind operation errors provide specific error messages."""

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

        # Mock the _apply_bulk_bind method to simulate an error during bind
        with mock.patch.object(
            admin_inst,
            '_apply_bulk_bind',
            side_effect=IntegrityError("Cannot bind due to constraint"),
        ):
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk, ext_2.pk],
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())

            # Should raise ValidationError from the bind operation
            with self.assertRaises(forms.ValidationError) as cm:
                form.save()

            error_message = str(cm.exception)
            self.assertIn("Cannot bind due to constraint", error_message)