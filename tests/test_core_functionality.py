"""Core functionality tests for the ReverseRelationAdminMixin.

This module contains tests for basic admin mixin functionality, form generation,
and field rendering capabilities.
"""
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
from .models import Extension, Service, Site, UniqueExtension
from .shared_test_base import BaseAdminMixinTestCase, DummySite


class CoreAdminMixinTests(BaseAdminMixinTestCase):
    """Test core admin mixin functionality, form generation, and field rendering."""

    def test_single_binding_syncs(self):
        """Test that single binding synchronization works correctly."""
        service = Service.objects.create(name="svc")
        a = Site.objects.create(name="A")
        b = Site.objects.create(name="B")

        request = self.factory.post("/")
        admin = ServiceAdmin(Service, self.site)
        form_cls = admin.get_form(request, service)

        form = form_cls({"site_binding": a.pk}, instance=service)
        self.assertTrue(form.is_valid())
        obj = form.save()
        self.assertEqual(Site.objects.get(pk=a.pk).service, obj)
        self.assertIsNone(Site.objects.get(pk=b.pk).service)

        # Change selection to B; A should unbind
        form = form_cls({"site_binding": b.pk}, instance=obj)
        self.assertTrue(form.is_valid())
        obj = form.save()
        self.assertEqual(Site.objects.get(pk=b.pk).service, obj)
        self.assertIsNone(Site.objects.get(pk=a.pk).service)

    def test_admin_without_declared_fieldsets_renders_virtual_fields(self):
        """Ensure admins that do not declare fieldsets still render reverse fields.

        get_form should derive fields from ModelForm when no fieldsets are declared,
        and our injected reverse fields must still be added.
        """
        service = Service.objects.create(name="svc")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            # No fieldsets declared
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                )
            }

        request = self.factory.get("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        # Instantiate the form; the injected field should exist
        form = form_cls(instance=service)
        self.assertIn("site_binding", form.fields)

    def test_admin_declares_fields_but_not_virtual_names_still_renders(self):
        """When admin declares `fields` (no fieldsets), get_fields appends virtual names.

        This ensures the template includes the reverse fields even if the
        admin didn't explicitly list them in `fields`.
        """
        service = Service.objects.create(name="svc")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            fields = ("name",)  # does not include the virtual field
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                )
            }

        request = self.factory.get("/")
        admin_inst = TempAdmin(Service, DummySite())
        # get_fields should include the virtual name
        names = admin_inst.get_fields(request, service)
        self.assertIn("site_binding", names)
        # Form should contain the injected field
        form_cls = admin_inst.get_form(request, service)
        form = form_cls(instance=service)
        self.assertIn("site_binding", form.fields)

    def test_multiple_binding_syncs(self):
        """Test that multiple binding synchronization works correctly."""
        service = Service.objects.create(name="svc")
        e1 = Extension.objects.create(number="1001")
        e2 = Extension.objects.create(number="1002")
        e3 = Extension.objects.create(number="1003")

        request = self.factory.post("/")
        admin = ServiceAdmin(Service, self.site)
        form_cls = admin.get_form(request, service)

        # Select e1 and e2
        form = form_cls({"assigned_extensions": [e1.pk, e2.pk]}, instance=service)
        self.assertTrue(form.is_valid())
        obj = form.save()
        self.assertEqual(
            set(Extension.objects.filter(service=obj).values_list("pk", flat=True)),
            {e1.pk, e2.pk},
        )

        # Switch to e2 and e3 (e1 should unbind)
        form = form_cls({"assigned_extensions": [e2.pk, e3.pk]}, instance=obj)
        self.assertTrue(form.is_valid())
        obj = form.save()
        self.assertEqual(
            set(Extension.objects.filter(service=obj).values_list("pk", flat=True)),
            {e2.pk, e3.pk},
        )

    def test_multi_select_unique_conflict_rolls_back(self):
        """Binding multiple rows to a unique-per-service model should fully rollback."""
        service = Service.objects.create(name="svc")

        # Define a temp admin that exposes a multi-select for a model that has a
        # uniqueness constraint on the FK, so selecting 2 will violate unique.
        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "unique_bindings": ReverseRelationConfig(
                    model=UniqueExtension,
                    fk_field="service",
                    label="Unique",
                    multiple=True,
                )
            }

        a = UniqueExtension.objects.create(number="1001")
        b = UniqueExtension.objects.create(number="1002")

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        form = form_cls({"name": service.name, "unique_bindings": [a.pk, b.pk]}, instance=service)
        # This should be invalid because OneToOneField cannot bind two rows to the same service.
        # The save should error and rollback.
        self.assertTrue(form.is_valid())
        with self.assertRaises(IntegrityError):
            form.save()

        # Ensure no partial updates persisted (transaction rolled back)
        self.assertIsNone(UniqueExtension.objects.get(pk=a.pk).service)
        self.assertIsNone(UniqueExtension.objects.get(pk=b.pk).service)

    def test_mid_update_error_rolls_back(self):
        """Simulate an exception during bind sequence; expect zero changes persist."""
        service = Service.objects.create(name="svc")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "unique_bindings": ReverseRelationConfig(
                    model=UniqueExtension,
                    fk_field="service",
                    label="Unique",
                    multiple=True,
                )
            }

        m = UniqueExtension
        x = m.objects.create(number="1001")
        y = m.objects.create(number="1002")
        z = m.objects.create(number="1003")

        call_count = {"n": 0}

        original_save = m.save

        def flaky_save(self, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("Simulated mid-update failure")
            return original_save(self, *args, **kwargs)

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        form = form_cls(
            {"name": service.name, "unique_bindings": [x.pk, y.pk, z.pk]},
            instance=service,
        )
        self.assertTrue(form.is_valid())

        with mock.patch.object(m, "save", new=flaky_save):
            with self.assertRaises(RuntimeError):
                form.save()

        # No objects should remain bound due to atomic rollback
        self.assertEqual(m.objects.filter(service=service).count(), 0)