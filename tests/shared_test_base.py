"""Shared test utilities and base classes for admin mixin tests."""

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

from .models import Extension, Service, Site, UniqueExtension


class DummySite(AdminSite):
    """Dummy admin site for testing purposes."""


class BaseAdminMixinTestCase(TestCase):
    """Base test case with common setup and utilities for admin mixin tests."""
    
    def setUp(self):
        """Set up common test fixtures."""
        self.site = DummySite()
        self.factory = RequestFactory()
        self.service = Service.objects.create(name="test-service")
    
    def create_test_extensions(self, count=3, service=None):
        """Create test Extension objects.
        
        Args:
            count: Number of extensions to create
            service: Service to bind extensions to (optional)
            
        Returns:
            List of created Extension objects
        """
        extensions = []
        for i in range(count):
            ext = Extension.objects.create(
                number=f"100{i + 1}",
                service=service
            )
            extensions.append(ext)
        return extensions
    
    def create_test_sites(self, count=2, service=None):
        """Create test Site objects.
        
        Args:
            count: Number of sites to create
            service: Service to bind sites to (optional)
            
        Returns:
            List of created Site objects
        """
        sites = []
        for i in range(count):
            site = Site.objects.create(
                name=f"Site {chr(65 + i)}",  # Site A, Site B, etc.
                service=service
            )
            sites.append(site)
        return sites
    
    def create_test_services(self, count=1):
        """Create test Service objects.
        
        Args:
            count: Number of services to create
            
        Returns:
            List of created Service objects
        """
        services = []
        for i in range(count):
            service = Service.objects.create(name=f"service-{i + 1}")
            services.append(service)
        return services
    
    def create_test_unique_extensions(self, count=2, service=None):
        """Create test UniqueExtension objects.
        
        Args:
            count: Number of unique extensions to create
            service: Service to bind unique extensions to (optional)
            
        Returns:
            List of created UniqueExtension objects
        """
        unique_extensions = []
        for i in range(count):
            unique_ext = UniqueExtension.objects.create(
                number=f"200{i + 1}",
                service=service
            )
            unique_extensions.append(unique_ext)
        return unique_extensions
    
    def create_parameterized_admin(self, bulk_enabled=False, **config_overrides):
        """Create admin with configurable bulk settings for parameterized tests.
        
        Args:
            bulk_enabled: Whether to enable bulk operations
            **config_overrides: Additional configuration overrides for reverse relations
            
        Returns:
            Admin class instance configured for testing
        """
        class ParameterizedServiceAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    bulk=bulk_enabled,
                    **config_overrides.get("site_binding", {})
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    ordering=("number",),
                    bulk=bulk_enabled,
                    **config_overrides.get("assigned_extensions", {})
                ),
            }
            
            fieldsets = (("Binding", {"fields": ("site_binding", "assigned_extensions")}),)
        
        return ParameterizedServiceAdmin(Service, self.site)
    
    def assert_widget_compatibility(self, widget_class, field_name, admin_instance=None):
        """Assert that a widget works correctly with reverse relation fields.
        
        Args:
            widget_class: Widget class to test
            field_name: Name of the reverse relation field
            admin_instance: Optional admin instance (creates default if None)
        """
        if admin_instance is None:
            admin_instance = self.create_parameterized_admin()
        
        request = self.factory.get("/")
        form_cls = admin_instance.get_form(request, self.service)
        form = form_cls(instance=self.service)
        
        # Assert field exists
        self.assertIn(field_name, form.fields)
        
        # Assert widget is of expected type
        field = form.fields[field_name]
        self.assertIsInstance(field.widget, widget_class)
        
        # Assert widget renders without error
        widget_html = field.widget.render(field_name, None)
        self.assertIsInstance(widget_html, str)
        self.assertGreater(len(widget_html), 0)
    
    def create_permission_test_scenario(self, policy_type="allow_all"):
        """Create standardized permission test scenarios.
        
        Args:
            policy_type: Type of permission scenario to create
                - "allow_all": Always allow access
                - "deny_all": Always deny access  
                - "staff_only": Allow only staff users
                - "callable": Function-based permission
                
        Returns:
            Dictionary with permission policy and test users
        """
        # Create test users
        regular_user = User.objects.create_user(
            username="regular", password="test", is_staff=False
        )
        staff_user = User.objects.create_user(
            username="staff", password="test", is_staff=True
        )
        
        if policy_type == "allow_all":
            policy = lambda request, obj, config, selection: True
        elif policy_type == "deny_all":
            policy = lambda request, obj, config, selection: False
        elif policy_type == "staff_only":
            policy = lambda request, obj, config, selection: getattr(request.user, "is_staff", False)
        elif policy_type == "callable":
            def custom_policy(request, obj, config, selection):
                """Custom permission policy for testing."""
                return hasattr(request.user, "username") and request.user.username.startswith("staff")
            policy = custom_policy
        else:
            raise ValueError(f"Unknown policy_type: {policy_type}")
        
        return {
            "policy": policy,
            "regular_user": regular_user,
            "staff_user": staff_user,
        }
    
    def create_large_dataset(self, count=100, model_type="extensions"):
        """Create large datasets for performance and edge case testing.
        
        Args:
            count: Number of objects to create
            model_type: Type of objects to create ("extensions", "sites", "services")
            
        Returns:
            List of created objects
        """
        objects = []
        
        if model_type == "extensions":
            for i in range(count):
                ext = Extension.objects.create(number=f"bulk-{i:04d}")
                objects.append(ext)
        elif model_type == "sites":
            for i in range(count):
                site = Site.objects.create(name=f"Bulk Site {i:04d}")
                objects.append(site)
        elif model_type == "services":
            for i in range(count):
                service = Service.objects.create(name=f"bulk-service-{i:04d}")
                objects.append(service)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")
        
        return objects
    
    def create_edge_case_data(self, scenario="empty_queryset"):
        """Create various edge case data scenarios for testing.
        
        Args:
            scenario: Type of edge case to create
                - "empty_queryset": No related objects available
                - "single_item": Only one related object available
                - "max_items": Maximum reasonable number of items
                - "invalid_data": Data that should cause validation errors
                - "complex_relationships": Complex model relationship scenarios
                
        Returns:
            Dictionary with scenario data and metadata
        """
        if scenario == "empty_queryset":
            # Clear all existing objects
            Extension.objects.all().delete()
            Site.objects.all().delete()
            return {"extensions": [], "sites": [], "description": "No objects available"}
        
        elif scenario == "single_item":
            # Create exactly one of each type
            Extension.objects.all().delete()
            Site.objects.all().delete()
            ext = Extension.objects.create(number="single-ext")
            site = Site.objects.create(name="Single Site")
            return {
                "extensions": [ext],
                "sites": [site],
                "description": "Single item available"
            }
        
        elif scenario == "max_items":
            # Create a large but reasonable number of items
            extensions = self.create_large_dataset(50, "extensions")
            sites = self.create_large_dataset(25, "sites")
            return {
                "extensions": extensions,
                "sites": sites,
                "description": "Maximum reasonable items"
            }
        
        elif scenario == "invalid_data":
            # Create data that should cause validation issues
            return {
                "invalid_pks": [99999, -1, "invalid"],
                "empty_strings": ["", None],
                "description": "Invalid data for validation testing"
            }
        
        elif scenario == "complex_relationships":
            # Create complex relationship scenarios
            service1 = Service.objects.create(name="complex-service-1")
            service2 = Service.objects.create(name="complex-service-2")
            
            # Extensions bound to different services
            ext1 = Extension.objects.create(number="complex-1", service=service1)
            ext2 = Extension.objects.create(number="complex-2", service=service2)
            ext3 = Extension.objects.create(number="complex-3")  # Unbound
            
            # Sites with mixed binding states
            site1 = Site.objects.create(name="Complex Site 1", service=service1)
            site2 = Site.objects.create(name="Complex Site 2")  # Unbound
            
            return {
                "services": [service1, service2],
                "extensions": [ext1, ext2, ext3],
                "sites": [site1, site2],
                "bound_extensions": [ext1, ext2],
                "unbound_extensions": [ext3],
                "bound_sites": [site1],
                "unbound_sites": [site2],
                "description": "Complex relationship scenarios"
            }
        
        else:
            raise ValueError(f"Unknown scenario: {scenario}")
    
    def create_widget_test_data(self, widget_type="select"):
        """Create test data optimized for widget compatibility testing.
        
        Args:
            widget_type: Type of widget being tested
                - "select": Single select widget
                - "radio": Radio select widget
                - "multiple": Multiple select widget
                - "checkbox": Checkbox multiple select widget
                
        Returns:
            Dictionary with test data and expected behaviors
        """
        # Create base test data
        extensions = self.create_test_extensions(5)
        sites = self.create_test_sites(3)
        
        if widget_type in ["select", "radio"]:
            return {
                "extensions": extensions,
                "sites": sites,
                "expected_single_select": True,
                "expected_multiple_select": False,
                "test_selections": [extensions[0].pk, sites[0].pk],
                "description": f"Data for {widget_type} widget testing"
            }
        
        elif widget_type in ["multiple", "checkbox"]:
            return {
                "extensions": extensions,
                "sites": sites,
                "expected_single_select": False,
                "expected_multiple_select": True,
                "test_selections": [
                    [extensions[0].pk, extensions[1].pk],
                    [sites[0].pk, sites[1].pk]
                ],
                "description": f"Data for {widget_type} widget testing"
            }
        
        else:
            raise ValueError(f"Unknown widget_type: {widget_type}")
    
    def create_validation_test_scenarios(self):
        """Create comprehensive validation test scenarios.
        
        Returns:
            Dictionary with various validation scenarios
        """
        # Create base data
        service = Service.objects.create(name="validation-service")
        extensions = self.create_test_extensions(3)
        sites = self.create_test_sites(2)
        
        return {
            "valid_single_selection": sites[0].pk,
            "valid_multiple_selection": [extensions[0].pk, extensions[1].pk],
            "invalid_pk": 99999,
            "invalid_type": "not-a-number",
            "empty_selection": None,
            "empty_multiple_selection": [],
            "mixed_valid_invalid": [extensions[0].pk, 99999],
            "service": service,
            "extensions": extensions,
            "sites": sites,
            "description": "Comprehensive validation scenarios"
        }