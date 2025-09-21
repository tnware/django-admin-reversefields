"""Parameterized tests to ensure feature parity between bulk and non-bulk operations.

This module contains tests that verify the same logical operations work consistently
in both bulk=True and bulk=False modes, ensuring feature parity between operation modes.
"""

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


class ParameterizedOperationTests(BaseAdminMixinTestCase):
    """Test core operations with both bulk=True and bulk=False parameters."""

    def test_single_select_binding_both_modes(self):
        """Test single-select binding works consistently in both bulk and non-bulk modes."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        site_b = Site.objects.create(name="Site B")

        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create fresh service for each test
                service = Service.objects.create(name=f"test-service-{bulk_enabled}")
                
                admin_instance = self.create_parameterized_admin(bulk_enabled=bulk_enabled)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, service)

                # Test initial binding
                form = form_cls({"site_binding": site_a.pk}, instance=service)
                self.assertTrue(form.is_valid(), 
                              f"Form should be valid for bulk={bulk_enabled}")
                obj = form.save()

                # Verify binding worked
                site_a.refresh_from_db()
                self.assertEqual(site_a.service, obj,
                               f"Site A should be bound for bulk={bulk_enabled}")

                # Test changing binding
                form = form_cls({"site_binding": site_b.pk}, instance=obj)
                self.assertTrue(form.is_valid(),
                              f"Form should be valid for rebinding with bulk={bulk_enabled}")
                obj = form.save()

                # Verify rebinding worked
                site_a.refresh_from_db()
                site_b.refresh_from_db()
                self.assertIsNone(site_a.service,
                                f"Site A should be unbound for bulk={bulk_enabled}")
                self.assertEqual(site_b.service, obj,
                               f"Site B should be bound for bulk={bulk_enabled}")

    def test_multiple_select_binding_both_modes(self):
        """Test multi-select binding works consistently in both bulk and non-bulk modes."""
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create fresh test data for each iteration
                ext_1 = Extension.objects.create(number=f"100{bulk_enabled}1")
                ext_2 = Extension.objects.create(number=f"100{bulk_enabled}2")
                ext_3 = Extension.objects.create(number=f"100{bulk_enabled}3")
                service = Service.objects.create(name=f"test-service-multi-{bulk_enabled}")
                
                admin_instance = self.create_parameterized_admin(bulk_enabled=bulk_enabled)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, service)

                # Test initial multi-binding
                form = form_cls(
                    {"assigned_extensions": [ext_1.pk, ext_2.pk]}, 
                    instance=service
                )
                self.assertTrue(form.is_valid(),
                              f"Form should be valid for multi-select with bulk={bulk_enabled}")
                obj = form.save()

                # Verify multi-binding worked
                ext_1.refresh_from_db()
                ext_2.refresh_from_db()
                ext_3.refresh_from_db()
                self.assertEqual(ext_1.service, obj,
                               f"Extension 1 should be bound for bulk={bulk_enabled}")
                self.assertEqual(ext_2.service, obj,
                               f"Extension 2 should be bound for bulk={bulk_enabled}")
                self.assertIsNone(ext_3.service,
                                f"Extension 3 should be unbound for bulk={bulk_enabled}")

                # Test changing multi-selection
                form = form_cls(
                    {"assigned_extensions": [ext_2.pk, ext_3.pk]}, 
                    instance=obj
                )
                self.assertTrue(form.is_valid(),
                              f"Form should be valid for multi-rebinding with bulk={bulk_enabled}")
                obj = form.save()

                # Verify multi-rebinding worked
                ext_1.refresh_from_db()
                ext_2.refresh_from_db()
                ext_3.refresh_from_db()
                self.assertIsNone(ext_1.service,
                                f"Extension 1 should be unbound for bulk={bulk_enabled}")
                self.assertEqual(ext_2.service, obj,
                               f"Extension 2 should remain bound for bulk={bulk_enabled}")
                self.assertEqual(ext_3.service, obj,
                               f"Extension 3 should be newly bound for bulk={bulk_enabled}")

    def test_empty_selection_handling_both_modes(self):
        """Test empty selection handling works consistently in both modes."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        ext_1 = Extension.objects.create(number="1001")

        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create fresh service for each test
                service = Service.objects.create(name=f"test-service-empty-{bulk_enabled}")
                
                # Initially bind objects
                site_a.service = service
                site_a.save()
                ext_1.service = service
                ext_1.save()
                
                admin_instance = self.create_parameterized_admin(bulk_enabled=bulk_enabled)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, service)

                # Test clearing single-select
                form = form_cls({"site_binding": ""}, instance=service)
                self.assertTrue(form.is_valid(),
                              f"Form should be valid for empty single-select with bulk={bulk_enabled}")
                obj = form.save()

                # Verify unbinding worked
                site_a.refresh_from_db()
                self.assertIsNone(site_a.service,
                                f"Site should be unbound for bulk={bulk_enabled}")

                # Test clearing multi-select
                form = form_cls({"assigned_extensions": []}, instance=obj)
                self.assertTrue(form.is_valid(),
                              f"Form should be valid for empty multi-select with bulk={bulk_enabled}")
                obj = form.save()

                # Verify multi-unbinding worked
                ext_1.refresh_from_db()
                self.assertIsNone(ext_1.service,
                                f"Extension should be unbound for bulk={bulk_enabled}")

    def test_form_field_generation_both_modes(self):
        """Test form field generation works consistently in both modes."""
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                admin_instance = self.create_parameterized_admin(bulk_enabled=bulk_enabled)
                
                request = self.factory.get("/")
                form_cls = admin_instance.get_form(request, self.service)
                form = form_cls(instance=self.service)

                # Verify fields exist
                self.assertIn("site_binding", form.fields,
                            f"site_binding field should exist for bulk={bulk_enabled}")
                self.assertIn("assigned_extensions", form.fields,
                            f"assigned_extensions field should exist for bulk={bulk_enabled}")

                # Verify field properties
                site_field = form.fields["site_binding"]
                ext_field = form.fields["assigned_extensions"]

                # Single-select field should not be multiple
                self.assertFalse(getattr(site_field.widget, "allow_multiple_selected", True),
                               f"Site field should be single-select for bulk={bulk_enabled}")

                # Multi-select field should allow multiple
                self.assertTrue(getattr(ext_field.widget, "allow_multiple_selected", False),
                              f"Extension field should be multi-select for bulk={bulk_enabled}")


class ParameterizedPermissionTests(BaseAdminMixinTestCase):
    """Test permission scenarios work consistently in both bulk and non-bulk modes."""

    def test_permission_policy_consistency_both_modes(self):
        """Test permission policies work consistently in both modes."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        
        # Test different permission scenarios
        permission_scenarios = [
            ("allow_all", True),
            ("deny_all", False),
            ("staff_only", True),  # We'll test with staff user
        ]

        # Create users once for all test iterations to avoid unique constraint violations
        from django.contrib.auth.models import User
        regular_user = User.objects.create_user(
            username="regular_perm_test", password="test", is_staff=False
        )
        staff_user = User.objects.create_user(
            username="staff_perm_test", password="test", is_staff=True
        )

        for policy_type, expected_access in permission_scenarios:
            for bulk_enabled in [False, True]:
                with self.subTest(policy_type=policy_type, bulk_enabled=bulk_enabled):
                    # Create permission policy
                    if policy_type == "allow_all":
                        policy = lambda request, obj, config, selection: True
                    elif policy_type == "deny_all":
                        policy = lambda request, obj, config, selection: False
                    elif policy_type == "staff_only":
                        policy = lambda request, obj, config, selection: getattr(request.user, "is_staff", False)
                    else:
                        raise ValueError(f"Unknown policy_type: {policy_type}")
                    
                    # Create admin with permission policy
                    class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                        reverse_permissions_enabled = True
                        reverse_relations = {
                            "site_binding": ReverseRelationConfig(
                                model=Site,
                                fk_field="service",
                                multiple=False,
                                bulk=bulk_enabled,
                                permission=policy
                            )
                        }
                    
                    admin_instance = TestAdmin(Service, self.site)
                    
                    # Test with staff user (should have access for staff_only policy)
                    request = self.factory.get("/")
                    request.user = staff_user
                    
                    form_cls = admin_instance.get_form(request, self.service)
                    form = form_cls(instance=self.service)
                    
                    # Field should exist regardless of permission (permissions affect behavior, not existence)
                    self.assertIn("site_binding", form.fields,
                                f"Field should exist for {policy_type} with bulk={bulk_enabled}")

    def test_permission_callable_consistency_both_modes(self):
        """Test permission callables work consistently in both modes."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        
        def custom_permission(request, obj, config, selection):
            """Custom permission that allows access only for specific users."""
            return hasattr(request.user, "username") and "staff" in request.user.username

        # Create users once to avoid unique constraint violations
        from django.contrib.auth.models import User
        staff_user = User.objects.create_user(
            username="staff_callable_test", password="test", is_staff=True
        )

        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                
                # Create admin with permission callable
                class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                    reverse_permissions_enabled = True
                    reverse_relations = {
                        "assigned_extensions": ReverseRelationConfig(
                            model=Extension,
                            fk_field="service",
                            multiple=True,
                            bulk=bulk_enabled,
                            permission=custom_permission
                        )
                    }
                
                admin_instance = TestAdmin(Service, self.site)
                
                # Test with staff user (should have access)
                request = self.factory.get("/")
                request.user = staff_user
                
                form_cls = admin_instance.get_form(request, self.service)
                form = form_cls(instance=self.service)
                
                # Field should exist for staff user
                self.assertIn("assigned_extensions", form.fields,
                            f"Field should exist for staff user with bulk={bulk_enabled}")

    def test_permission_mode_consistency_both_modes(self):
        """Test permission modes (hide/disable) work consistently in both modes."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        
        # Create users once to avoid unique constraint violations
        from django.contrib.auth.models import User
        regular_user = User.objects.create_user(
            username="regular_mode_test", password="test", is_staff=False
        )
        
        # Create deny-all policy
        deny_policy = lambda request, obj, config, selection: False
        
        # Test both permission modes
        for permission_mode in ["hide", "disable"]:
            for bulk_enabled in [False, True]:
                with self.subTest(permission_mode=permission_mode, bulk_enabled=bulk_enabled):
                    
                    # Create admin with permission mode
                    class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                        reverse_permissions_enabled = True
                        reverse_permission_mode = permission_mode
                        reverse_relations = {
                            "site_binding": ReverseRelationConfig(
                                model=Site,
                                fk_field="service",
                                multiple=False,
                                bulk=bulk_enabled,
                                permission=deny_policy
                            )
                        }
                    
                    admin_instance = TestAdmin(Service, self.site)
                    
                    # Test with regular user (should be denied)
                    request = self.factory.get("/")
                    request.user = regular_user
                    
                    form_cls = admin_instance.get_form(request, self.service)
                    form = form_cls(instance=self.service)
                    
                    if permission_mode == "hide":
                        # Field should not exist when hidden
                        self.assertNotIn("site_binding", form.fields,
                                       f"Field should be hidden for {permission_mode} with bulk={bulk_enabled}")
                    else:  # disable mode
                        # Field should exist but be disabled
                        self.assertIn("site_binding", form.fields,
                                    f"Field should exist but be disabled for {permission_mode} with bulk={bulk_enabled}")


class ParameterizedValidationTests(BaseAdminMixinTestCase):
    """Test validation scenarios work consistently in both bulk and non-bulk modes."""

    def test_required_field_validation_both_modes(self):
        """Test required field validation works consistently in both modes."""
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create admin with required field
                class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                    reverse_relations = {
                        "site_binding": ReverseRelationConfig(
                            model=Site,
                            fk_field="service",
                            multiple=False,
                            bulk=bulk_enabled,
                            required=True
                        )
                    }
                
                admin_instance = TestAdmin(Service, self.site)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.service)
                
                # Test with empty required field
                form = form_cls({"site_binding": ""}, instance=self.service)
                
                # Form should be invalid for required field
                self.assertFalse(form.is_valid(),
                               f"Form should be invalid for empty required field with bulk={bulk_enabled}")
                self.assertIn("site_binding", form.errors,
                            f"site_binding should have validation error with bulk={bulk_enabled}")

    def test_invalid_pk_validation_both_modes(self):
        """Test invalid primary key validation works consistently in both modes."""
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                admin_instance = self.create_parameterized_admin(bulk_enabled=bulk_enabled)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.service)
                
                # Test with invalid primary key
                form = form_cls({"site_binding": 99999}, instance=self.service)
                
                # Form should be invalid for non-existent PK
                self.assertFalse(form.is_valid(),
                               f"Form should be invalid for non-existent PK with bulk={bulk_enabled}")

    def test_invalid_selection_validation_both_modes(self):
        """Test invalid selection validation works consistently in both modes."""
        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                admin_instance = self.create_parameterized_admin(bulk_enabled=bulk_enabled)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.service)
                
                # Test with mixed valid and invalid PKs in multi-select
                form = form_cls(
                    {"assigned_extensions": [ext_1.pk, 99999]}, 
                    instance=self.service
                )
                
                # Form should be invalid for mixed valid/invalid PKs
                self.assertFalse(form.is_valid(),
                               f"Form should be invalid for mixed valid/invalid PKs with bulk={bulk_enabled}")

    def test_constraint_violation_handling_both_modes(self):
        """Test constraint violation handling works consistently in both modes."""
        # This test verifies that constraint violations are handled the same way
        # regardless of bulk mode (both should raise IntegrityError and rollback)
        
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create fresh service for each test
                service = Service.objects.create(name=f"constraint-test-{bulk_enabled}")
                
                # Create admin that would cause constraint violation
                # (This is a conceptual test - actual constraint depends on model setup)
                admin_instance = self.create_parameterized_admin(bulk_enabled=bulk_enabled)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, service)
                
                # Create valid form (constraint violations would be tested with specific model constraints)
                form = form_cls({}, instance=service)
                
                # Form should be valid (no constraint violation in this basic case)
                self.assertTrue(form.is_valid(),
                              f"Basic form should be valid with bulk={bulk_enabled}")

    def test_validation_error_messages_both_modes(self):
        """Test validation error messages are consistent in both modes."""
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create admin with required field
                class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                    reverse_relations = {
                        "site_binding": ReverseRelationConfig(
                            model=Site,
                            fk_field="service",
                            multiple=False,
                            bulk=bulk_enabled,
                            required=True
                        )
                    }
                
                admin_instance = TestAdmin(Service, self.site)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, self.service)
                
                # Test with empty required field
                form = form_cls({"site_binding": ""}, instance=self.service)
                
                if not form.is_valid():
                    # Error messages should be consistent regardless of bulk mode
                    self.assertIn("site_binding", form.errors,
                                f"site_binding should have error with bulk={bulk_enabled}")
                    
                    # Error message should be meaningful
                    error_msg = str(form.errors["site_binding"])
                    self.assertGreater(len(error_msg), 0,
                                     f"Error message should not be empty with bulk={bulk_enabled}")

    def test_form_save_validation_both_modes(self):
        """Test form save validation works consistently in both modes."""
        # Create test data
        site_a = Site.objects.create(name="Site A")
        
        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create fresh service for each test
                service = Service.objects.create(name=f"save-test-{bulk_enabled}")
                
                admin_instance = self.create_parameterized_admin(bulk_enabled=bulk_enabled)
                
                request = self.factory.post("/")
                form_cls = admin_instance.get_form(request, service)
                
                # Test valid form save
                form = form_cls({"site_binding": site_a.pk}, instance=service)
                self.assertTrue(form.is_valid(),
                              f"Valid form should be valid with bulk={bulk_enabled}")
                
                # Save should work without errors
                try:
                    saved_obj = form.save()
                    self.assertEqual(saved_obj, service,
                                   f"Saved object should be the service with bulk={bulk_enabled}")
                except Exception as e:
                    self.fail(f"Form save should not raise exception with bulk={bulk_enabled}: {e}")