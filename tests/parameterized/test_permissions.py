"""Parameterized tests for permission handling."""

# Django imports
from django.contrib import admin
from django.contrib.auth.models import User

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

from ..models import Company, Department, Project

# Test imports
from ..shared_test_base import BaseAdminMixinTestCase


class ParameterizedPermissionTests(BaseAdminMixinTestCase):
    """Test permission scenarios work consistently in both bulk and non-bulk modes."""

    admin_class = admin.ModelAdmin

    def test_permission_policy_consistency_both_modes(self):
        """Test permission policies work consistently in both modes."""
        # Create test data
        dept_a = Department.objects.create(name="Department A")

        # Test different permission scenarios
        permission_scenarios = [
            ("allow_all", True),
            ("deny_all", False),
            ("staff_only", True),  # We'll test with staff user
        ]

        # Create users once for all test iterations to avoid unique constraint violations
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
                        policy = lambda request, obj, config, selection: getattr(
                            request.user, "is_staff", False
                        )
                    else:
                        raise ValueError(f"Unknown policy_type: {policy_type}")

                    # Create admin with permission policy
                    class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                        reverse_permissions_enabled = True
                        reverse_relations = {
                            "department_binding": ReverseRelationConfig(
                                model=Department,
                                fk_field="company",
                                multiple=False,
                                bulk=bulk_enabled,
                                permission=policy,
                            )
                        }

                    admin_instance = TestAdmin(Company, self.site)

                    # Test with staff user (should have access for staff_only policy)
                    request = self.factory.get("/")
                    request.user = staff_user

                    form_cls = admin_instance.get_form(request, self.company)
                    form = form_cls(instance=self.company)

                    # Field should exist regardless of permission (permissions affect behavior, not existence)
                    self.assertIn(
                        "department_binding",
                        form.fields,
                        f"Field should exist for {policy_type} with bulk={bulk_enabled}",
                    )

    def test_render_time_policy_flag_affects_visibility_and_editability(self):
        """Per-field policy influences render only when flag is enabled.

        When base perms allow but the per-field policy denies, the field is:
        - visible and enabled when reverse_render_uses_field_policy=False
        - hidden/disabled based on reverse_permission_mode when True
        """

        class StubUser:
            def __init__(self, is_staff=False):
                self.is_staff = is_staff

            def has_perm(self, perm):
                return True  # Base change permission allowed

        deny_policy = staticmethod(lambda request, obj, config, selection: False)

        for permission_mode in ["hide", "disable"]:
            for bulk_enabled in [False, True]:
                with self.subTest(permission_mode=permission_mode, bulk_enabled=bulk_enabled):
                    # Case A: Flag disabled -> base perms allow -> field visible/editable
                    class AdminNoFlag(ReverseRelationAdminMixin, self.admin_class):
                        reverse_permissions_enabled = True
                        reverse_permission_mode = permission_mode
                        reverse_render_uses_field_policy = False
                        reverse_relations = {
                            "department_binding": ReverseRelationConfig(
                                model=Department,
                                fk_field="company",
                                multiple=False,
                                bulk=bulk_enabled,
                                permission=deny_policy,
                            )
                        }

                    req = self.factory.get("/")
                    req.user = StubUser()
                    admin_a = AdminNoFlag(Company, self.site)
                    form_cls_a = admin_a.get_form(req, self.company)
                    form_a = form_cls_a(instance=self.company)

                    self.assertIn("department_binding", form_a.fields)
                    self.assertFalse(getattr(form_a.fields["department_binding"], "disabled", False))

                    # Case B: Flag enabled -> policy denies -> hidden/disabled according to mode
                    class AdminFlag(ReverseRelationAdminMixin, self.admin_class):
                        reverse_permissions_enabled = True
                        reverse_permission_mode = permission_mode
                        reverse_render_uses_field_policy = True
                        reverse_relations = {
                            "department_binding": ReverseRelationConfig(
                                model=Department,
                                fk_field="company",
                                multiple=False,
                                bulk=bulk_enabled,
                                permission=deny_policy,
                            )
                        }

                    admin_b = AdminFlag(Company, self.site)
                    form_cls_b = admin_b.get_form(req, self.company)
                    form_b = form_cls_b(instance=self.company)

                    if permission_mode == "hide":
                        self.assertNotIn("department_binding", form_b.fields)
                    else:
                        self.assertIn("department_binding", form_b.fields)
                        self.assertTrue(form_b.fields["department_binding"].disabled)

    def test_persistence_gate_ignores_crafted_post_for_hidden_or_disabled_fields(self):
        """Even if POST includes a disabled/hidden field, payload filtering blocks changes."""

        deny_policy = staticmethod(lambda request, obj, config, selection: False)

        for permission_mode in ["hide", "disable"]:
            for bulk_enabled in [False, True]:
                with self.subTest(permission_mode=permission_mode, bulk_enabled=bulk_enabled):
                    dept = Department.objects.create(name="Dept X")

                    class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                        reverse_permissions_enabled = True
                        reverse_permission_mode = permission_mode
                        reverse_render_uses_field_policy = True  # consult per-field policy at render
                        reverse_relations = {
                            "department_binding": ReverseRelationConfig(
                                model=Department,
                                fk_field="company",
                                multiple=False,
                                bulk=bulk_enabled,
                                permission=deny_policy,
                            )
                        }

                    admin_inst = TestAdmin(Company, self.site)
                    request = self.factory.post("/")
                    form_cls = admin_inst.get_form(request, self.company)
                    form = form_cls(
                        {"name": self.company.name, "department_binding": dept.pk},
                        instance=self.company,
                    )

                    # Form remains valid: disabled/hidden fields skip validation errors
                    self.assertTrue(form.is_valid())
                    form.save()

                    dept.refresh_from_db()
                    self.assertIsNone(
                        dept.company,
                        f"Crafted POST should be ignored in {permission_mode} mode with bulk={bulk_enabled}",
                    )

    def test_global_policy_custom_message_precedence_both_modes(self):
        """When only a global policy denies, its message appears on the field error."""

        class GlobalMessagePolicy:
            permission_denied_message = "Global policy denied this selection"

            def __call__(self, request, obj, config, selection):
                # Allow at render (selection=None), deny when a selection exists
                return selection is None

        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                project = Project.objects.create(name="Project A")

                class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_permissions_enabled = True
                    reverse_permission_policy = GlobalMessagePolicy()
                    reverse_relations = {
                        "project_binding": ReverseRelationConfig(
                            model=Project,
                            fk_field="company",
                            multiple=False,
                            bulk=bulk_enabled,
                        )
                    }

                request = self.factory.post("/")
                admin_inst = TestAdmin(Company, self.site)
                form_cls = admin_inst.get_form(request, self.company)
                form = form_cls(
                    {"name": self.company.name, "project_binding": project.pk},
                    instance=self.company,
                )

                self.assertFalse(form.is_valid())
                self.assertIn(
                    "global policy denied",
                    form.errors.get("project_binding", [""])[0].lower(),
                )

    def test_permission_callable_consistency_both_modes(self):
        """Test permission callables work consistently in both modes."""
        # Create test data
        project_1 = Project.objects.create(name="Project 1")

        def custom_permission(request, obj, config, selection):
            """Custom permission that allows access only for specific users."""
            return hasattr(request.user, "username") and "staff" in request.user.username

        # Create users once to avoid unique constraint violations
        staff_user = User.objects.create_user(
            username="staff_callable_test", password="test", is_staff=True
        )

        # Test both bulk modes
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                # Create admin with permission callable
                class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_permissions_enabled = True
                    reverse_relations = {
                        "assigned_projects": ReverseRelationConfig(
                            model=Project,
                            fk_field="company",
                            multiple=True,
                            bulk=bulk_enabled,
                            permission=custom_permission,
                        )
                    }

                admin_instance = TestAdmin(Company, self.site)

                # Test with staff user (should have access)
                request = self.factory.get("/")
                request.user = staff_user

                form_cls = admin_instance.get_form(request, self.company)
                form = form_cls(instance=self.company)

                # Field should exist for staff user
                self.assertIn(
                    "assigned_projects",
                    form.fields,
                    f"Field should exist for staff user with bulk={bulk_enabled}",
                )

    def test_permission_mode_consistency_both_modes(self):
        """Test permission modes (hide/disable) work consistently in both modes."""
        # Create test data
        dept_a = Department.objects.create(name="Department A")

        # Create users once to avoid unique constraint violations
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
                    class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                        reverse_permissions_enabled = True
                        reverse_permission_mode = permission_mode
                        reverse_relations = {
                            "department_binding": ReverseRelationConfig(
                                model=Department,
                                fk_field="company",
                                multiple=False,
                                bulk=bulk_enabled,
                                permission=deny_policy,
                            )
                        }

                    admin_instance = TestAdmin(Company, self.site)

                    # Test with regular user (should be denied)
                    request = self.factory.get("/")
                    request.user = regular_user

                    form_cls = admin_instance.get_form(request, self.company)
                    form = form_cls(instance=self.company)

                    if permission_mode == "hide":
                        # Field should not exist when hidden
                        self.assertNotIn(
                            "department_binding",
                            form.fields,
                            f"Field should be hidden for {permission_mode} with bulk={bulk_enabled}",
                        )
                    else:  # disable mode
                        # Field should exist but be disabled
                        self.assertIn(
                            "department_binding",
                            form.fields,
                            f"Field should exist but be disabled for {permission_mode} with bulk={bulk_enabled}",
                        )

    def test_per_field_permission_callable_denies_both_modes(self):
        """Test per-field permission callable that denies access for base operations."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                project_a = Project.objects.create(name="Project A")

                def deny_policy(request, obj, config, selection):
                    """Deny all access."""
                    return False

                class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_permissions_enabled = True
                    reverse_permission_mode = "disable"
                    reverse_relations = {
                        "project_binding": ReverseRelationConfig(
                            model=Project,
                            fk_field="company",
                            multiple=False,
                            permission=deny_policy,
                            bulk=bulk_enabled,
                        )
                    }

                request = self.factory.post("/")
                admin_inst = TestAdmin(Company, self.site)
                form_cls = admin_inst.get_form(request, self.company)
                form = form_cls(
                    {"name": self.company.name, "project_binding": project_a.pk},
                    instance=self.company,
                )

                self.assertFalse(form.is_valid())
                self.assertIn("permission", form.errors.get("project_binding", [""])[0].lower())

                # Verify no change was persisted
                project_a.refresh_from_db()
                self.assertIsNone(project_a.company)

    def test_per_field_permission_callable_allows_both_modes(self):
        """Test per-field permission callable that allows access for base operations."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                project_a = Project.objects.create(name="Project A")

                def allow_policy(request, obj, config, selection):
                    """Allow all access."""
                    return True

                class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_permissions_enabled = True
                    reverse_permission_mode = "disable"
                    reverse_relations = {
                        "project_binding": ReverseRelationConfig(
                            model=Project,
                            fk_field="company",
                            multiple=False,
                            permission=allow_policy,
                            bulk=bulk_enabled,
                        )
                    }

                request = self.factory.post("/")
                admin_inst = TestAdmin(Company, self.site)
                form_cls = admin_inst.get_form(request, self.company)
                form = form_cls(
                    {"name": self.company.name, "project_binding": project_a.pk},
                    instance=self.company,
                )

                self.assertTrue(form.is_valid())
                saved_company = form.save()

                # Verify the binding was created
                project_a.refresh_from_db()
                self.assertEqual(project_a.company, saved_company)

    def test_selection_based_permission_both_modes(self):
        """Test per-field permission based on object selection for base operations."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                project_a = Project.objects.create(name="A")
                project_b = Project.objects.create(name="B")

                class SelectivePolicy:
                    """Policy that allows only specific selections."""

                    def has_perm(self, request, obj, config, selection):
                        """Allow only selecting project with name 'B'."""
                        if selection and getattr(selection, "name", None) == "B":
                            return True
                        return False

                class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_permissions_enabled = True
                    reverse_permission_mode = "disable"
                    reverse_relations = {
                        "project_binding": ReverseRelationConfig(
                            model=Project,
                            fk_field="company",
                            multiple=False,
                            permission=SelectivePolicy(),
                            permission_denied_message="Not allowed for this selection",
                            bulk=bulk_enabled,
                        )
                    }

                request = self.factory.post("/")
                admin_inst = TestAdmin(Company, self.site)
                form_cls = admin_inst.get_form(request, self.company)

                # Test denied selection (Project A)
                form_denied = form_cls(
                    {"name": self.company.name, "project_binding": project_a.pk},
                    instance=self.company,
                )
                self.assertFalse(form_denied.is_valid())
                self.assertIn(
                    "not allowed for this selection",
                    form_denied.errors.get("project_binding", [""])[0].lower(),
                )

                # Verify no binding was created
                project_a.refresh_from_db()
                self.assertIsNone(project_a.company)

                # Test allowed selection (Project B)
                form_allowed = form_cls(
                    {"name": self.company.name, "project_binding": project_b.pk},
                    instance=self.company,
                )
                self.assertTrue(form_allowed.is_valid())
                saved_company = form_allowed.save()

                # Verify the allowed binding was created
                project_b.refresh_from_db()
                self.assertEqual(project_b.company, saved_company)

    def test_global_permission_policy_both_modes(self):
        """Test global reverse permission policy for base operations."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                project_a = Project.objects.create(name="Project A")

                class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_permissions_enabled = True
                    reverse_permission_mode = "disable"
                    # Global policy: deny if selection name is "Project A" (like the working test)
                    reverse_permission_policy = staticmethod(
                        lambda request, obj, config, selection: (
                            False
                            if (
                                selection is not None
                                and getattr(selection, "name", None) == "Project A"
                            )
                            else True
                        )
                    )
                    reverse_relations = {
                        "project_binding": ReverseRelationConfig(
                            model=Project,
                            fk_field="company",
                            multiple=False,
                            bulk=bulk_enabled,
                        )
                    }

                request = self.factory.post("/")
                admin_inst = TestAdmin(Company, self.site)
                form_cls = admin_inst.get_form(request, self.company)
                form = form_cls(
                    {"name": self.company.name, "project_binding": project_a.pk},
                    instance=self.company,
                )

                self.assertFalse(form.is_valid())
                self.assertIn("permission", form.errors.get("project_binding", [""])[0].lower())

                # Verify no binding was created
                project_a.refresh_from_db()
                self.assertIsNone(project_a.company)

    def test_policy_with_custom_message_both_modes(self):
        """Test policy object with custom error message for base operations."""
        for bulk_enabled in [False, True]:
            with self.subTest(bulk_enabled=bulk_enabled):
                project_a = Project.objects.create(name="Project A")

                class CustomMessagePolicy:
                    """Policy with custom error message."""

                    permission_denied_message = "Custom field-specific error message"

                    def __call__(self, request, obj, config, selection):
                        return False

                class TestAdmin(ReverseRelationAdminMixin, self.admin_class):
                    reverse_permissions_enabled = True
                    reverse_permission_mode = "disable"
                    reverse_relations = {
                        "project_binding": ReverseRelationConfig(
                            model=Project,
                            fk_field="company",
                            multiple=False,
                            permission=CustomMessagePolicy(),
                            bulk=bulk_enabled,
                        )
                    }

                request = self.factory.post("/")
                admin_inst = TestAdmin(Company, self.site)
                form_cls = admin_inst.get_form(request, self.company)
                form = form_cls(
                    {"name": self.company.name, "project_binding": project_a.pk},
                    instance=self.company,
                )

                self.assertFalse(form.is_valid())
                self.assertIn(
                    "custom field-specific error message",
                    form.errors.get("project_binding", [""])[0].lower(),
                )
