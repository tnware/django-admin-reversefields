"""Test suite for permission handling and policies."""

# Standard library imports
from unittest import mock

# Django imports
from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied

# Project imports
from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

# Test imports
from .models import Extension, Service, Site
from .shared_test_base import BaseAdminMixinTestCase, DummySite


class PermissionTests(BaseAdminMixinTestCase):
    """Test suite for permission handling and policies."""

    def test_bulk_operations_respect_reverse_permission_policy(self):
        """Test that bulk operations respect ReversePermissionPolicy."""

        class TestPermissionPolicy:
            """Test permission policy that denies access."""
            permission_denied_message = "Access denied by test policy"

            def has_perm(self, request, obj, config, selection):
                # Deny access for testing
                return False

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_permission_policy = TestPermissionPolicy()
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

        # Mock has_reverse_change_permission to return False (permission denied)
        with mock.patch.object(admin_inst, 'has_reverse_change_permission', return_value=False):
            form.save()

            # Verify that no bulk operations were performed due to permission denial
            # Extensions should not be bound to the service
            self.assertEqual(Extension.objects.filter(service=self.service).count(), 0)

    def test_revoked_reverse_field_permission_preserves_existing_bindings(self):
        """Existing bindings remain when a field is removed from the authorized payload."""

        for bulk in (False, True):
            with self.subTest(bulk=bulk):
                site = Site.objects.create(name=f"Site bulk {int(bulk)}", service=self.service)

                class PermissionGuardAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                    reverse_permissions_enabled = True
                    reverse_render_uses_field_policy = True
                    reverse_relations = {
                        "site_binding": ReverseRelationConfig(
                            model=Site,
                            fk_field="service",
                            multiple=False,
                            bulk=bulk,
                        )
                    }

                    def has_reverse_change_permission(  # type: ignore[override]
                        self,
                        request,
                        obj,
                        config,
                        selection=None,
                    ) -> bool:
                        return False

                request = self.factory.post("/")
                admin_inst = PermissionGuardAdmin(Service, self.site)
                form_cls = admin_inst.get_form(request, self.service)
                form = form_cls({"name": self.service.name}, instance=self.service)
                self.assertTrue(form.is_valid())
                form.save()

                site.refresh_from_db()
                self.assertEqual(site.service, self.service)

    def test_bulk_operations_permission_checks_applied_before_operations(self):
        """Test that permission checks are applied before bulk operations."""

        class TestPermissionPolicy:
            """Test permission policy that allows access."""

            def has_perm(self, request, obj, config, selection):
                # Allow access for testing
                return True

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_permission_policy = TestPermissionPolicy()
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

        # Track permission check calls
        permission_check_calls = []
        original_has_permission = admin_inst.has_reverse_change_permission

        def track_permission_check(request, obj, config, selection=None):
            permission_check_calls.append((config.model.__name__, selection))
            return original_has_permission(request, obj, config, selection)

        with mock.patch.object(
            admin_inst, 'has_reverse_change_permission', side_effect=track_permission_check
        ):
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk, ext_2.pk],
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that permission checks were called before bulk operations
            self.assertGreater(len(permission_check_calls), 0,
                             "Permission checks should be called before bulk operations")

            # Verify the permission check was called for the Extension model
            extension_checks = [call for call in permission_check_calls if call[0] == 'Extension']
            self.assertGreater(len(extension_checks), 0,
                             "Permission check should be called for Extension model")

    def test_bulk_operations_permission_denied_scenarios(self):
        """Test permission-denied scenarios with bulk operations."""

        class DenyAllPolicy:
            """Permission policy that denies all access."""
            permission_denied_message = "Bulk operations not allowed"

            def has_perm(self, request, obj, config, selection):
                return False

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_permission_policy = DenyAllPolicy()
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,
                ),
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,
                )
            }

        ext_1 = Extension.objects.create(number="1001")
        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk],
                "site_binding": site_a.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify that no bulk operations were performed due to permission denial
        # Extension should not be bound to the service
        self.assertEqual(Extension.objects.filter(service=self.service).count(), 0)
        # Site should not be bound to the service
        self.assertIsNone(Site.objects.get(pk=site_a.pk).service)

    def test_bulk_operations_with_per_field_permission_policy(self):
        """Test bulk operations with per-field permission policies."""
        
        class AllowAllPolicy:
            """Policy that allows all operations."""
            
            def has_perm(self, request, obj, config, selection):
                return True
        
        class DenyAllPolicy:
            """Policy that denies all operations."""
            permission_denied_message = "Operations not allowed"
            
            def has_perm(self, request, obj, config, selection):
                return False
        
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_render_uses_field_policy = True  # Enable per-field policies for rendering
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,
                    permission=AllowAllPolicy(),
                ),
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,
                    permission=DenyAllPolicy(),
                )
            }

        ext_1 = Extension.objects.create(number="1001")
        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Create form instance to check field permissions
        form = form_cls(instance=self.service)
        
        # Verify that extensions field is enabled (permission allowed)
        self.assertFalse(form.fields["assigned_extensions"].disabled)
        
        # Verify that site_binding field is disabled (permission denied)
        self.assertTrue(form.fields["site_binding"].disabled)

        # Test form with only allowed field data (disabled fields should be ignored)
        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk],
                # Don't include site_binding data since it's disabled
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()
        
        # Verify that extensions were allowed (bulk operation succeeded)
        self.assertEqual(Extension.objects.filter(service=self.service).count(), 1)
        self.assertEqual(Extension.objects.get(pk=ext_1.pk).service, self.service)
        
        # Verify that site binding was not affected (field was disabled)
        self.assertIsNone(Site.objects.get(pk=site_a.pk).service)

    def test_bulk_operations_with_callable_permission_policy(self):
        """Test bulk operations with callable permission policies."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            
            @staticmethod
            def allow_extensions_only(request, obj, config, selection):
                """Callable permission policy that allows only extensions."""
                return config.model == Extension
            
            reverse_permission_policy = allow_extensions_only
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,
                ),
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    bulk=True,
                )
            }

        ext_1 = Extension.objects.create(number="1001")
        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        form = form_cls(
            {
                "name": self.service.name,
                "assigned_extensions": [ext_1.pk],
                "site_binding": site_a.pk,
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())
        form.save()

        # Verify that extensions were allowed (bulk operation succeeded)
        self.assertEqual(Extension.objects.filter(service=self.service).count(), 1)
        self.assertEqual(Extension.objects.get(pk=ext_1.pk).service, self.service)

        # Verify that site binding was denied (bulk operation blocked)
        self.assertIsNone(Site.objects.get(pk=site_a.pk).service)

    def test_bulk_operations_with_object_has_perm_policy(self):
        """Test bulk operations with object that has has_perm method."""

        class ObjectWithHasPerm:
            """Object with has_perm method for permission checking."""

            def has_perm(self, request, obj, config, selection):
                # Allow all operations for testing
                return True

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_permission_policy = ObjectWithHasPerm()
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,
                )
            }

        ext_1 = Extension.objects.create(number="1001")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Track has_perm calls
        has_perm_calls = []
        original_has_perm = admin_inst.reverse_permission_policy.has_perm

        def track_has_perm(request, obj, config, selection):
            has_perm_calls.append((config.model.__name__, selection))
            return original_has_perm(request, obj, config, selection)

        with mock.patch.object(
            admin_inst.reverse_permission_policy, 'has_perm', side_effect=track_has_perm
        ):
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk],
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that has_perm was called
            self.assertGreater(len(has_perm_calls), 0,
                             "has_perm should be called for permission checking")

            # Verify that bulk operation succeeded
            self.assertEqual(Extension.objects.filter(service=self.service).count(), 1)
            self.assertEqual(Extension.objects.get(pk=ext_1.pk).service, self.service)

    def test_permissions_disable_mode_disables_field_and_ignores_post(self):
        """Test that disable mode disables field and ignores POST data."""
        service = Service.objects.create(name="svc")
        a = Site.objects.create(name="A")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permission_mode = "disable"
            reverse_permissions_enabled = True
            reverse_render_uses_field_policy = True
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    required=True,
                    permission_denied_message="You do not have permission to choose this value.",
                )
            }

            def has_reverse_change_permission(self, request, obj, config, selection=None) -> bool:  # type: ignore[override]
                return False

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        form = form_cls({"name": service.name, "site_binding": a.pk}, instance=service)
        # Field should be present but disabled; previously, required=True could have caused
        # a validation error. Our mixin sets required=False when disabling, so it's valid.
        self.assertTrue(form.is_valid())
        form.save()
        self.assertIsNone(Site.objects.get(pk=a.pk).service)

    def test_permissions_disable_mode_required_field_without_initial_would_error_without_fix(self):
        """Demonstrate that a disabled required field with no initial would be invalid without fix.

        With the mixin's change (required=False when disabling), the form should now be valid.
        """
        service = Service.objects.create(name="svc")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permission_mode = "disable"
            reverse_permissions_enabled = True
            # Force denial at render gate so the field is actually disabled
            reverse_render_uses_field_policy = True
            reverse_permission_policy = staticmethod(lambda request, obj, config, selection: False)
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    required=True,
                )
            }

            def has_reverse_change_permission(self, request, obj, config, selection=None) -> bool:  # type: ignore[override]
                return False

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        # No initial binding exists. Post no selection.
        form = form_cls({"name": service.name, "site_binding": ""}, instance=service)
        # Without the fix, Django would raise "This field is required." on a disabled field.
        # With the fix, the form should be valid.
        self.assertTrue(form.is_valid())

    def test_permissions_hide_mode_removes_field(self):
        """Test that hide mode removes field from form."""
        service = Service.objects.create(name="svc")
        a = Site.objects.create(name="A")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permission_mode = "hide"
            reverse_permissions_enabled = True
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                )
            }

            def has_reverse_change_permission(self, request, obj, config, selection=None) -> bool:  # type: ignore[override]
                return False

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        form = form_cls({"name": service.name, "site_binding": a.pk}, instance=service)
        # Field is not in the form (hidden); still valid and ignored
        self.assertTrue(form.is_valid())
        form.save()
        self.assertIsNone(Site.objects.get(pk=a.pk).service)

    def test_permissions_unsupported_mode_is_handled_gracefully(self):
        """Test that unsupported permission modes are handled gracefully."""
        service = Service.objects.create(name="svc")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permission_mode = "raise"
            reverse_permissions_enabled = True
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                )
            }

            def has_reverse_change_permission(self, request, obj, config, selection=None) -> bool:  # type: ignore[override]
                return False

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        # 'raise' is not a supported mode; current behavior treats it like disable/hide.
        admin_inst.get_form(request, service)

    def test_per_field_permission_callable_denies(self):
        """Test per-field permission callable that denies access."""
        service = Service.objects.create(name="svc")
        a = Site.objects.create(name="A")

        def deny_policy(request, obj, config, selection):
            return False

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_permission_mode = "disable"
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    clean=None,
                    permission=deny_policy,
                )
            }

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        form = form_cls({"name": service.name, "site_binding": a.pk}, instance=service)
        self.assertFalse(form.is_valid())
        self.assertIn("permission", form.errors.get("site_binding", [""])[0].lower())
        # No change persisted
        self.assertIsNone(Site.objects.get(pk=a.pk).service)

    def test_per_field_permission_object_selection_based(self):
        """Test per-field permission based on object selection."""
        service = Service.objects.create(name="svc")
        a = Site.objects.create(name="A")
        b = Site.objects.create(name="B")

        class Policy:
            def has_perm(self, request, obj, config, selection):
                # allow only selecting site with name "B"
                if selection and getattr(selection, "name", None) == "B":
                    return True
                return False

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_permission_mode = "disable"
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    clean=None,
                    permission=Policy(),
                    permission_denied_message="Not allowed for this selection",
                )
            }

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        # Attempt to set A (denied) – should add a field error via clean
        form = form_cls({"name": service.name, "site_binding": a.pk}, instance=service)
        self.assertFalse(form.is_valid())
        self.assertIn("Not allowed for this selection", form.errors.get("site_binding", [""])[0])
        self.assertIsNone(Site.objects.get(pk=a.pk).service)

        # Set B (allowed)
        form2 = form_cls({"name": service.name, "site_binding": b.pk}, instance=service)
        self.assertTrue(form2.is_valid())
        obj = form2.save()
        self.assertEqual(Site.objects.get(pk=b.pk).service, obj)

    def test_global_reverse_permission_policy_callable(self):
        """Test global reverse permission policy with callable."""
        service = Service.objects.create(name="svc")
        a = Site.objects.create(name="A")

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_permission_mode = "disable"
            # Global policy: deny if selection name is "A"
            reverse_permission_policy = staticmethod(
                lambda request, obj, config, selection: (
                    False
                    if (selection is not None and getattr(selection, "name", None) == "A")
                    else True
                )
            )
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                )
            }

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        form = form_cls({"name": service.name, "site_binding": a.pk}, instance=service)
        self.assertFalse(form.is_valid())
        self.assertIn("permission", form.errors.get("site_binding", [""])[0].lower())

    def test_policy_object_message_is_used_when_field_has_no_override(self):
        """Test that policy object message is used when field has no override."""
        service = Service.objects.create(name="svc")
        a = Site.objects.create(name="A")

        class DenyPolicy:
            permission_denied_message = "Custom deny message from policy"

            def __call__(self, request, obj, config, selection):
                return False

        class TempAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_permissions_enabled = True
            reverse_permission_mode = "disable"
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    multiple=False,
                    permission=DenyPolicy(),
                )
            }

        request = self.factory.post("/")
        admin_inst = TempAdmin(Service, DummySite())
        form_cls = admin_inst.get_form(request, service)
        form = form_cls({"name": service.name, "site_binding": a.pk}, instance=service)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "custom deny message from policy",
            form.errors.get("site_binding", [""])[0].lower(),
        )

    def test_bulk_permission_error_during_operations(self):
        """Test permission errors during bulk operations."""

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

        # Mock the queryset filter and update methods to simulate a permission error
        with mock.patch.object(Extension._default_manager, 'filter') as mock_filter:
            mock_queryset = mock.Mock()
            mock_queryset.update.side_effect = PermissionDenied("Database permission denied")
            mock_filter.return_value = mock_queryset

            # Should raise ValidationError with meaningful message
            with self.assertRaises(forms.ValidationError) as cm:
                form.save()

            error_message = str(cm.exception)
            # The error message format depends on which bulk operation fails
            self.assertTrue(
                "Bulk operation failed" in error_message or
                "Unexpected error during bulk" in error_message
            )
            self.assertIn("Database permission denied", error_message)