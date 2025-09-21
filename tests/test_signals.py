"""Test suite for signal bypassing behavior in bulk operations."""

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


class SignalBypassTests(BaseAdminMixinTestCase):
    """Test suite for signal bypassing behavior in bulk operations."""

    def test_bulk_operations_bypass_pre_save_signals(self):
        """Test that bulk operations don't trigger pre_save signals."""
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

        # Set up signal tracking
        pre_save_calls = []

        def track_pre_save(sender, instance, **kwargs):
            pre_save_calls.append(instance)

        from django.db.models.signals import pre_save
        pre_save.connect(track_pre_save, sender=Site)

        try:
            request = self.factory.post("/")
            admin_inst = TestAdmin(Service, self.site)
            form_cls = admin_inst.get_form(request, self.service)

            # Change selection from site_a to site_b using bulk operations
            form = form_cls(
                {
                    "name": self.service.name,
                    "site_binding": site_b.pk,
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that pre_save signals were NOT triggered for bulk operations
            # The signal should not be called because bulk operations use .update()
            self.assertEqual(len(pre_save_calls), 0,
                           "pre_save signals should not be triggered during bulk operations")

        finally:
            # Clean up signal connection
            pre_save.disconnect(track_pre_save, sender=Site)

    def test_bulk_operations_bypass_post_save_signals(self):
        """Test that bulk operations don't trigger post_save signals."""
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

        # Set up signal tracking
        post_save_calls = []

        def track_post_save(sender, instance, created, **kwargs):
            post_save_calls.append((instance, created))

        from django.db.models.signals import post_save
        post_save.connect(track_post_save, sender=Extension)

        try:
            request = self.factory.post("/")
            admin_inst = TestAdmin(Service, self.site)
            form_cls = admin_inst.get_form(request, self.service)

            # Bind multiple extensions using bulk operations
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk, ext_2.pk, ext_3.pk],
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that post_save signals were NOT triggered for bulk operations
            # The signal should not be called because bulk operations use .update()
            self.assertEqual(len(post_save_calls), 0,
                           "post_save signals should not be triggered during bulk operations")

        finally:
            # Clean up signal connection
            post_save.disconnect(track_post_save, sender=Extension)

    def test_individual_operations_still_trigger_pre_save_signals(self):
        """Test that individual operations still trigger pre_save signals when bulk=False."""
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
                    bulk=False,  # Use individual operations (existing behavior)
                )
            }

        # Set up signal tracking
        pre_save_calls = []

        def track_pre_save(sender, instance, **kwargs):
            pre_save_calls.append(instance)

        from django.db.models.signals import pre_save
        pre_save.connect(track_pre_save, sender=Site)

        try:
            request = self.factory.post("/")
            admin_inst = TestAdmin(Service, self.site)
            form_cls = admin_inst.get_form(request, self.service)

            # Change selection from site_a to site_b using individual operations
            form = form_cls(
                {
                    "name": self.service.name,
                    "site_binding": site_b.pk,
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that pre_save signals WERE triggered for individual operations
            # Should have at least one call (for the bind operation)
            self.assertGreater(len(pre_save_calls), 0,
                             "pre_save signals should be triggered during individual operations")

            # Verify the signal was called for the correct instances
            signal_instances = [call for call in pre_save_calls]
            self.assertTrue(any(isinstance(instance, Site) for instance in signal_instances),
                          "pre_save should be called for Site instances")

        finally:
            # Clean up signal connection
            pre_save.disconnect(track_pre_save, sender=Site)

    def test_individual_operations_still_trigger_post_save_signals(self):
        """Test that individual operations still trigger post_save signals when bulk=False."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=False,  # Use individual operations (existing behavior)
                )
            }

        # Set up signal tracking
        post_save_calls = []

        def track_post_save(sender, instance, created, **kwargs):
            post_save_calls.append((instance, created))

        from django.db.models.signals import post_save
        post_save.connect(track_post_save, sender=Extension)

        try:
            request = self.factory.post("/")
            admin_inst = TestAdmin(Service, self.site)
            form_cls = admin_inst.get_form(request, self.service)

            # Bind extensions using individual operations
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk, ext_2.pk],
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that post_save signals WERE triggered for individual operations
            # Should have at least one call (for the bind operations)
            self.assertGreater(len(post_save_calls), 0,
                             "post_save signals should be triggered during individual operations")

            # Verify the signal was called for the correct instances
            signal_instances = [call[0] for call in post_save_calls]
            self.assertTrue(any(isinstance(instance, Extension) for instance in signal_instances),
                          "post_save should be called for Extension instances")

        finally:
            # Clean up signal connection
            post_save.disconnect(track_post_save, sender=Extension)

    def test_mixed_bulk_and_individual_signal_behavior(self):
        """Test signal behavior when mixing bulk and individual configurations."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,  # Bulk operations - should bypass signals
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=False,  # Individual operations - should trigger signals
                ),
            }

        # Set up signal tracking for both models
        site_pre_save_calls = []
        extension_pre_save_calls = []

        def track_site_pre_save(sender, instance, **kwargs):
            site_pre_save_calls.append(instance)

        def track_extension_pre_save(sender, instance, **kwargs):
            extension_pre_save_calls.append(instance)

        from django.db.models.signals import pre_save
        pre_save.connect(track_site_pre_save, sender=Site)
        pre_save.connect(track_extension_pre_save, sender=Extension)

        try:
            request = self.factory.post("/")
            admin_inst = TestAdmin(Service, self.site)
            form_cls = admin_inst.get_form(request, self.service)

            # Update both fields simultaneously
            form = form_cls(
                {
                    "name": self.service.name,
                    "site_binding": site_a.pk,  # Bulk operation
                    "assigned_extensions": [ext_1.pk, ext_2.pk],  # Individual operations
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that Site signals were NOT triggered (bulk=True)
            self.assertEqual(len(site_pre_save_calls), 0,
                           "Site pre_save signals should not be triggered (bulk=True)")

            # Verify that Extension signals WERE triggered (bulk=False)
            self.assertGreater(len(extension_pre_save_calls), 0,
                             "Extension pre_save signals should be triggered (bulk=False)")

        finally:
            # Clean up signal connections
            pre_save.disconnect(track_site_pre_save, sender=Site)
            pre_save.disconnect(track_extension_pre_save, sender=Extension)

    def test_bulk_operations_with_custom_signals(self):
        """Test that bulk operations bypass custom model signals as well."""
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

        # Set up custom signal tracking
        custom_signal_calls = []

        def track_custom_signal(sender, instance, **kwargs):
            custom_signal_calls.append(instance)

        # Create a custom signal and connect it
        from django.dispatch import Signal
        custom_signal = Signal()

        # Mock the Site model's save method to emit custom signal
        original_save = Site.save

        def custom_save(self, *args, **kwargs):
            result = original_save(self, *args, **kwargs)
            custom_signal.send(sender=Site, instance=self)
            return result

        Site.save = custom_save
        custom_signal.connect(track_custom_signal, sender=Site)

        try:
            request = self.factory.post("/")
            admin_inst = TestAdmin(Service, self.site)
            form_cls = admin_inst.get_form(request, self.service)

            # Bind site using bulk operations
            form = form_cls(
                {
                    "name": self.service.name,
                    "site_binding": site_a.pk,
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that custom signals were NOT triggered (because save() wasn't called)
            self.assertEqual(len(custom_signal_calls), 0,
                           "Custom signals should not be triggered during bulk operations")

        finally:
            # Clean up
            Site.save = original_save
            custom_signal.disconnect(track_custom_signal, sender=Site)