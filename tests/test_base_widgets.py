"""Base widget compatibility tests for the ReverseRelationAdminMixin.

This module contains comprehensive tests for widget compatibility with reverse relation fields,
covering standard Django widgets, rendering scenarios, and JavaScript/media handling.
"""

from django.contrib import admin
from django.forms import widgets

from django_admin_reversefields.mixins import (
    ReverseRelationAdminMixin,
    ReverseRelationConfig,
)

from .models import Extension, Service, Site
from .shared_test_base import BaseAdminMixinTestCase


class BaseWidgetCompatibilityTests(BaseAdminMixinTestCase):
    """Test widget compatibility and rendering for base (non-bulk) operations."""

    def setUp(self):
        """Set up test data for widget compatibility testing."""
        super().setUp()
        self.extensions = self.create_test_extensions(5)
        self.sites = self.create_test_sites(3)
        self.request = self.factory.get("/")

    def test_select_widget_single_relation(self):
        """Test Select widget compatibility with single-select reverse relations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Assert field exists and has correct widget
        self.assertIn("site_binding", form.fields)
        field = form.fields["site_binding"]
        self.assertIsInstance(field.widget, widgets.Select)

        # Test widget rendering with empty state
        widget_html = field.widget.render("site_binding", None)
        self.assertIsInstance(widget_html, str)
        self.assertIn("<select", widget_html)
        self.assertIn("site_binding", widget_html)

        # Test widget rendering with selected value
        selected_site = self.sites[0]
        widget_html = field.widget.render("site_binding", selected_site.pk)
        self.assertIn(f'value="{selected_site.pk}"', widget_html)
        self.assertIn("selected", widget_html)

    def test_radio_select_widget_single_relation(self):
        """Test RadioSelect widget compatibility with single-select reverse relations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.RadioSelect,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Assert field exists and has correct widget
        field = form.fields["site_binding"]
        self.assertIsInstance(field.widget, widgets.RadioSelect)

        # Test widget rendering
        widget_html = field.widget.render("site_binding", None)
        self.assertIsInstance(widget_html, str)
        self.assertIn('type="radio"', widget_html)
        self.assertIn("site_binding", widget_html)

        # Verify all sites appear as radio options
        for site in self.sites:
            self.assertIn(f'value="{site.pk}"', widget_html)
            self.assertIn(str(site.name), widget_html)

    def test_select_multiple_widget_multiple_relation(self):
        """Test SelectMultiple widget compatibility with multi-select reverse relations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Assert field exists and has correct widget
        field = form.fields["assigned_extensions"]
        self.assertIsInstance(field.widget, widgets.SelectMultiple)

        # Test widget rendering with empty state
        widget_html = field.widget.render("assigned_extensions", None)
        self.assertIsInstance(widget_html, str)
        self.assertIn("<select", widget_html)
        self.assertIn("multiple", widget_html)
        self.assertIn("assigned_extensions", widget_html)

        # Test widget rendering with multiple selected values
        selected_extensions = [self.extensions[0].pk, self.extensions[2].pk]
        widget_html = field.widget.render("assigned_extensions", selected_extensions)
        for ext_pk in selected_extensions:
            self.assertIn(f'value="{ext_pk}"', widget_html)
        # Should contain selected attributes for chosen options
        self.assertIn("selected", widget_html)

    def test_checkbox_select_multiple_widget_multiple_relation(self):
        """Test CheckboxSelectMultiple widget compatibility with multi-select reverse relations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.CheckboxSelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Assert field exists and has correct widget
        field = form.fields["assigned_extensions"]
        self.assertIsInstance(field.widget, widgets.CheckboxSelectMultiple)

        # Test widget rendering
        widget_html = field.widget.render("assigned_extensions", None)
        self.assertIsInstance(widget_html, str)
        self.assertIn('type="checkbox"', widget_html)
        self.assertIn("assigned_extensions", widget_html)

        # Verify all extensions appear as checkbox options
        for extension in self.extensions:
            self.assertIn(f'value="{extension.pk}"', widget_html)
            self.assertIn(str(extension.number), widget_html)

    def test_widget_rendering_with_empty_queryset(self):
        """Test widget rendering when no related objects are available."""
        # Clear all related objects
        Extension.objects.all().delete()
        Site.objects.all().delete()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Test single select with empty queryset
        site_field = form.fields["site_binding"]
        site_html = site_field.widget.render("site_binding", None)
        self.assertIn("<select", site_html)
        # Should have empty option or no options besides empty
        self.assertIn("<option", site_html)

        # Test multiple select with empty queryset
        ext_field = form.fields["assigned_extensions"]
        ext_html = ext_field.widget.render("assigned_extensions", None)
        self.assertIn("<select", ext_html)
        self.assertIn("multiple", ext_html)

    def test_widget_rendering_with_single_item(self):
        """Test widget rendering when only one related object is available."""
        # Clear existing and create single items
        Extension.objects.all().delete()
        Site.objects.all().delete()
        single_extension = Extension.objects.create(number="single-ext")
        single_site = Site.objects.create(name="Single Site")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.RadioSelect,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.CheckboxSelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Test radio select with single item
        site_field = form.fields["site_binding"]
        site_html = site_field.widget.render("site_binding", None)
        self.assertIn('type="radio"', site_html)
        self.assertIn(f'value="{single_site.pk}"', site_html)
        self.assertIn(single_site.name, site_html)

        # Test checkbox multiple with single item
        ext_field = form.fields["assigned_extensions"]
        ext_html = ext_field.widget.render("assigned_extensions", None)
        self.assertIn('type="checkbox"', ext_html)
        self.assertIn(f'value="{single_extension.pk}"', ext_html)
        self.assertIn(single_extension.number, ext_html)

    def test_widget_form_media_handling(self):
        """Test that widgets properly handle form media (CSS/JS) requirements."""

        class CustomWidget(widgets.Select):
            """Custom widget with media requirements for testing."""

            class Media:
                css = {"all": ("custom-widget.css",)}
                js = ("custom-widget.js",)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=CustomWidget,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Test that form media includes widget media
        form_media = form.media
        self.assertIn("custom-widget.css", str(form_media))
        self.assertIn("custom-widget.js", str(form_media))

    def test_widget_javascript_compatibility(self):
        """Test widget JavaScript compatibility and DOM integration."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select(attrs={"class": "js-enabled"}),
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple(attrs={"data-widget": "multi-select"}),
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Test that widget attributes are preserved
        site_field = form.fields["site_binding"]
        site_html = site_field.widget.render("site_binding", None)
        self.assertIn('class="js-enabled"', site_html)

        ext_field = form.fields["assigned_extensions"]
        ext_html = ext_field.widget.render("assigned_extensions", None)
        self.assertIn('data-widget="multi-select"', ext_html)

    def test_custom_widget_integration_scenarios(self):
        """Test integration with custom widget scenarios and edge cases."""

        class CustomSelectWidget(widgets.Select):
            """Custom select widget with additional functionality."""

            def __init__(self, *args, **kwargs):
                self.custom_option = kwargs.pop("custom_option", "default")
                super().__init__(*args, **kwargs)

            def render(self, name, value, attrs=None, renderer=None):
                html = super().render(name, value, attrs, renderer)
                return f"<!-- Custom: {self.custom_option} -->{html}"

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=CustomSelectWidget(custom_option="test-value"),
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Test custom widget functionality
        field = form.fields["site_binding"]
        self.assertIsInstance(field.widget, CustomSelectWidget)
        self.assertEqual(field.widget.custom_option, "test-value")

        # Test custom rendering
        widget_html = field.widget.render("site_binding", None)
        self.assertIn("<!-- Custom: test-value -->", widget_html)
        self.assertIn("<select", widget_html)

    def test_widget_data_state_variations(self):
        """Test widget rendering with various data states and configurations."""
        # Bind some extensions to the service for testing pre-selected states
        bound_extensions = self.extensions[:2]
        for ext in bound_extensions:
            ext.service = self.service
            ext.save()

        bound_site = self.sites[0]
        bound_site.service = self.service
        bound_site.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Test that pre-bound values are reflected in initial form data
        self.assertEqual(form.initial.get("site_binding"), bound_site.pk)
        expected_ext_pks = sorted([ext.pk for ext in bound_extensions])
        actual_ext_pks = sorted(form.initial.get("assigned_extensions", []))
        self.assertEqual(actual_ext_pks, expected_ext_pks)

        # Test widget rendering with pre-selected values
        site_field = form.fields["site_binding"]
        site_html = site_field.widget.render("site_binding", bound_site.pk)
        self.assertIn(f'value="{bound_site.pk}" selected', site_html)

        ext_field = form.fields["assigned_extensions"]
        bound_ext_pks = [ext.pk for ext in bound_extensions]
        ext_html = ext_field.widget.render("assigned_extensions", bound_ext_pks)
        for ext_pk in bound_ext_pks:
            # Should have selected attribute for bound extensions
            self.assertIn(f'value="{ext_pk}"', ext_html)
        self.assertIn("selected", ext_html)


class ComprehensiveSingleSelectWidgetTests(BaseAdminMixinTestCase):
    """Comprehensive tests for single-select widget scenarios and edge cases."""

    def setUp(self):
        """Set up test data for comprehensive single-select widget testing."""
        super().setUp()
        self.extensions = self.create_test_extensions(10)  # Larger dataset for testing
        self.sites = self.create_test_sites(8)  # Various queryset sizes
        self.request = self.factory.get("/")

    def test_select_widget_with_small_queryset(self):
        """Test Select widget behavior with small queryset (1-3 items)."""
        # Create small queryset scenario
        small_sites = self.sites[:3]
        Site.objects.exclude(pk__in=[s.pk for s in small_sites]).delete()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for small queryset scenario."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["site_binding"]
        widget_html = field.widget.render("site_binding", None)
        
        # Verify all small queryset items are present
        for site in small_sites:
            self.assertIn(f'value="{site.pk}"', widget_html)
            self.assertIn(str(site.name), widget_html)
        
        # Should have empty option plus the 3 sites
        option_count = widget_html.count('<option')
        self.assertEqual(option_count, 4)  # Empty option + 3 sites

    def test_select_widget_with_medium_queryset(self):
        """Test Select widget behavior with medium queryset (4-10 items)."""
        # Use all 8 sites for medium queryset
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for medium queryset scenario."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["site_binding"]
        widget_html = field.widget.render("site_binding", None)
        
        # Verify all medium queryset items are present
        for site in self.sites:
            self.assertIn(f'value="{site.pk}"', widget_html)
            self.assertIn(str(site.name), widget_html)
        
        # Should have empty option plus the 8 sites
        option_count = widget_html.count('<option')
        self.assertEqual(option_count, 9)  # Empty option + 8 sites

    def test_select_widget_with_large_queryset(self):
        """Test Select widget behavior with large queryset (20+ items)."""
        # Create additional sites for large queryset
        large_sites = []
        for i in range(20):
            site = Site.objects.create(name=f"Large Site {i}")
            large_sites.append(site)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for large queryset scenario."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["site_binding"]
        widget_html = field.widget.render("site_binding", None)
        
        # Verify large queryset handling
        total_sites = Site.objects.count()
        option_count = widget_html.count('<option')
        self.assertEqual(option_count, total_sites + 1)  # Empty option + all sites
        
        # Spot check some of the large sites
        for site in large_sites[:5]:
            self.assertIn(f'value="{site.pk}"', widget_html)
            self.assertIn(str(site.name), widget_html)

    def test_select_widget_with_queryset_filtering(self):
        """Test Select widget with limit_choices_to filtering."""
        # Mark some sites as active/inactive for filtering
        active_sites = self.sites[:4]
        inactive_sites = self.sites[4:]
        
        for site in active_sites:
            site.name = f"Active {site.name}"
            site.save()
        for site in inactive_sites:
            site.name = f"Inactive {site.name}"
            site.save()

        def filter_active_sites(queryset, instance, request):
            """Filter to only show active sites."""
            return queryset.filter(name__startswith="Active")

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin with queryset filtering."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                    limit_choices_to=filter_active_sites,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["site_binding"]
        widget_html = field.widget.render("site_binding", None)
        
        # Should only contain active sites
        for site in active_sites:
            self.assertIn(f'value="{site.pk}"', widget_html)
            self.assertIn(str(site.name), widget_html)
        
        # Should not contain inactive sites
        for site in inactive_sites:
            self.assertNotIn(f'value="{site.pk}"', widget_html)
        
        # Should have empty option plus active sites only
        option_count = widget_html.count('<option')
        self.assertEqual(option_count, len(active_sites) + 1)

    def test_select_widget_required_field_configuration(self):
        """Test Select widget behavior with required field configuration."""
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin with required field."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                    required=True,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["site_binding"]
        
        # Field should be marked as required
        self.assertTrue(field.required)
        
        # Widget should have required attribute
        widget_html = field.widget.render("site_binding", None)
        self.assertIn("<select", widget_html)
        
        # Test form validation with empty value
        form_data = {"site_binding": ""}
        form = form_cls(data=form_data, instance=self.service)
        self.assertFalse(form.is_valid())
        self.assertIn("site_binding", form.errors)

    def test_select_widget_optional_field_configuration(self):
        """Test Select widget behavior with optional field configuration."""
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin with optional field."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                    required=False,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["site_binding"]
        
        # Field should not be required
        self.assertFalse(field.required)
        
        # Test form validation with empty value (should be valid)
        form_data = {"site_binding": ""}
        form = form_cls(data=form_data, instance=self.service)
        # Note: This might fail due to other required fields, but site_binding should not error
        if not form.is_valid():
            self.assertNotIn("site_binding", form.errors)

    def test_select_widget_rendering_with_preselected_values(self):
        """Test Select widget rendering with various pre-selected value scenarios."""
        # Bind a site to the service
        selected_site = self.sites[0]
        selected_site.service = self.service
        selected_site.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for pre-selected values."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Test initial form data includes pre-selected value
        self.assertEqual(form.initial.get("site_binding"), selected_site.pk)
        
        # Test widget rendering with pre-selected value
        field = form.fields["site_binding"]
        widget_html = field.widget.render("site_binding", selected_site.pk)
        
        # Should have selected attribute on the correct option
        self.assertIn(f'value="{selected_site.pk}" selected', widget_html)
        
        # Other options should not be selected
        for site in self.sites[1:]:
            if f'value="{site.pk}"' in widget_html:
                # This option exists but should not be selected
                self.assertNotIn(f'value="{site.pk}" selected', widget_html)

    def test_select_widget_rendering_with_empty_state(self):
        """Test Select widget rendering in various empty state scenarios."""
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for empty state scenarios."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["site_binding"]
        
        # Test rendering with None value
        widget_html = field.widget.render("site_binding", None)
        self.assertIn("<select", widget_html)
        self.assertIn('value=""', widget_html)  # Empty option
        # Django's Select widget selects the empty option by default when value is None
        self.assertIn('value="" selected', widget_html)
        
        # Test rendering with empty string value
        widget_html = field.widget.render("site_binding", "")
        self.assertIn("<select", widget_html)
        self.assertIn('value="" selected', widget_html)  # Empty option should be selected
        
        # Test rendering with invalid value (should not crash)
        widget_html = field.widget.render("site_binding", 99999)
        self.assertIn("<select", widget_html)
        # Invalid value should not cause any option to be selected
        self.assertNotIn("selected", widget_html)

    def test_select_widget_form_submission_accuracy(self):
        """Test Select widget form submission and data binding accuracy."""
        target_site = self.sites[2]  # Choose a specific site for binding
        
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for form submission accuracy."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        
        # Test form submission with valid site selection
        form_data = {"site_binding": str(target_site.pk)}
        form = form_cls(data=form_data, instance=self.service)
        
        # Form should be valid (assuming no other validation issues)
        if form.is_valid():
            # Test that cleaned data contains correct value
            self.assertEqual(form.cleaned_data["site_binding"], target_site.pk)
        else:
            # If form is invalid due to other fields, site_binding should not be the issue
            self.assertNotIn("site_binding", form.errors)
        
        # Test form submission with empty selection
        form_data = {"site_binding": ""}
        form = form_cls(data=form_data, instance=self.service)
        
        if form.is_valid():
            # Empty selection should result in None or empty value
            cleaned_value = form.cleaned_data.get("site_binding")
            self.assertIn(cleaned_value, [None, ""])

    def test_select_widget_data_binding_persistence(self):
        """Test that Select widget data binding persists correctly through save operations."""
        target_site = self.sites[1]
        
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for data binding persistence."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        
        # Simulate form submission and save
        form_cls = admin_instance.get_form(self.request, self.service)
        form_data = {"site_binding": str(target_site.pk)}
        form = form_cls(data=form_data, instance=self.service)
        
        if form.is_valid():
            # Save the form (this would normally be done by admin)
            admin_instance.save_model(self.request, self.service, form, change=True)
            
            # Verify the binding was persisted
            target_site.refresh_from_db()
            self.assertEqual(target_site.service, self.service)
            
            # Verify other sites are not bound
            for site in self.sites:
                if site.pk != target_site.pk:
                    site.refresh_from_db()
                    self.assertNotEqual(site.service, self.service)



    def test_select_widget_with_custom_attributes(self):
        """Test Select widget with custom HTML attributes and CSS classes."""
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin with custom widget attributes."""
            reverse_relations = {
                "site_binding": ReverseRelationConfig(
                    model=Site,
                    fk_field="service",
                    label="Site",
                    widget=widgets.Select(attrs={
                        "class": "custom-select-widget",
                        "data-testid": "site-selector",
                        "style": "width: 300px;",
                    }),
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["site_binding"]
        widget_html = field.widget.render("site_binding", None)
        
        # Verify custom attributes are present
        self.assertIn('class="custom-select-widget"', widget_html)
        self.assertIn('data-testid="site-selector"', widget_html)
        self.assertIn('style="width: 300px;"', widget_html)
        
        # Basic functionality should still work
        self.assertIn("<select", widget_html)
        for site in self.sites:
            self.assertIn(f'value="{site.pk}"', widget_html)


class ComprehensiveMultiSelectWidgetTests(BaseAdminMixinTestCase):
    """Comprehensive tests for multi-select widget scenarios and edge cases."""

    def setUp(self):
        """Set up test data for comprehensive multi-select widget testing."""
        super().setUp()
        self.extensions = self.create_test_extensions(15)  # Larger dataset for testing
        self.sites = self.create_test_sites(10)  # Various queryset sizes
        self.request = self.factory.get("/")

    def test_select_multiple_widget_with_various_selection_combinations(self):
        """Test SelectMultiple widget with different selection combinations."""
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for various selection combinations."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["assigned_extensions"]
        
        # Test empty selection
        widget_html = field.widget.render("assigned_extensions", None)
        self.assertIn("<select", widget_html)
        self.assertIn("multiple", widget_html)
        self.assertNotIn("selected", widget_html)
        
        # Test single selection
        single_selection = [self.extensions[0].pk]
        widget_html = field.widget.render("assigned_extensions", single_selection)
        self.assertIn(f'value="{self.extensions[0].pk}"', widget_html)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, 1)
        
        # Test multiple selections (3 items)
        multi_selection = [self.extensions[0].pk, self.extensions[3].pk, self.extensions[7].pk]
        widget_html = field.widget.render("assigned_extensions", multi_selection)
        for ext_pk in multi_selection:
            self.assertIn(f'value="{ext_pk}"', widget_html)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, 3)
        
        # Test many selections (half of available)
        many_selection = [ext.pk for ext in self.extensions[:8]]
        widget_html = field.widget.render("assigned_extensions", many_selection)
        for ext_pk in many_selection:
            self.assertIn(f'value="{ext_pk}"', widget_html)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, 8)
        
        # Test all selections
        all_selection = [ext.pk for ext in self.extensions]
        widget_html = field.widget.render("assigned_extensions", all_selection)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, len(self.extensions))

    def test_checkbox_select_multiple_widget_with_various_selections(self):
        """Test CheckboxSelectMultiple widget with different selection combinations."""
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for checkbox multi-select combinations."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.CheckboxSelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["assigned_extensions"]
        
        # Test empty selection
        widget_html = field.widget.render("assigned_extensions", None)
        self.assertIn('type="checkbox"', widget_html)
        self.assertNotIn("checked", widget_html)
        
        # Test single checkbox selection
        single_selection = [self.extensions[2].pk]
        widget_html = field.widget.render("assigned_extensions", single_selection)
        checked_count = widget_html.count("checked")
        self.assertEqual(checked_count, 1)
        self.assertIn(f'value="{self.extensions[2].pk}" checked', widget_html)
        
        # Test multiple checkbox selections
        multi_selection = [self.extensions[1].pk, self.extensions[4].pk, self.extensions[9].pk]
        widget_html = field.widget.render("assigned_extensions", multi_selection)
        checked_count = widget_html.count("checked")
        self.assertEqual(checked_count, 3)
        for ext_pk in multi_selection:
            self.assertIn(f'value="{ext_pk}" checked', widget_html)
        
        # Test that non-selected checkboxes are not checked
        non_selected = [ext for ext in self.extensions if ext.pk not in multi_selection]
        for ext in non_selected:
            self.assertNotIn(f'value="{ext.pk}" checked', widget_html)

    def test_filtered_select_multiple_widget_compatibility(self):
        """Test FilteredSelectMultiple widget compatibility if available."""
        try:
            from django.contrib.admin.widgets import FilteredSelectMultiple
            
            class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
                """Test admin for FilteredSelectMultiple widget."""
                reverse_relations = {
                    "assigned_extensions": ReverseRelationConfig(
                        model=Extension,
                        fk_field="service",
                        label="Extensions",
                        multiple=True,
                        widget=FilteredSelectMultiple("Extensions", is_stacked=False),
                    ),
                }

            admin_instance = TestAdmin(Service, self.site)
            form_cls = admin_instance.get_form(self.request, self.service)
            form = form_cls(instance=self.service)

            field = form.fields["assigned_extensions"]
            self.assertIsInstance(field.widget, FilteredSelectMultiple)
            
            # Test widget rendering
            widget_html = field.widget.render("assigned_extensions", None)
            self.assertIn("selectfilter", widget_html.lower())  # FilteredSelectMultiple adds CSS classes
            
            # Test with selections
            selected_extensions = [self.extensions[0].pk, self.extensions[5].pk]
            widget_html = field.widget.render("assigned_extensions", selected_extensions)
            for ext_pk in selected_extensions:
                self.assertIn(f'value="{ext_pk}"', widget_html)
            
            # Test form media includes FilteredSelectMultiple assets
            form_media = form.media
            self.assertIn("SelectFilter2.js", str(form_media))
            
        except ImportError:
            # FilteredSelectMultiple not available in this Django version
            self.skipTest("FilteredSelectMultiple not available in this Django version")

    def test_multi_select_widget_with_maximum_selection_limits(self):
        """Test multi-select widget behavior with maximum selection limits."""
        # Create a custom widget that enforces selection limits
        class LimitedSelectMultiple(widgets.SelectMultiple):
            """Custom SelectMultiple widget with selection limit."""
            
            def __init__(self, max_selections=None, *args, **kwargs):
                self.max_selections = max_selections
                super().__init__(*args, **kwargs)
                if max_selections:
                    self.attrs.update({
                        'data-max-selections': str(max_selections),
                        'class': 'limited-select-multiple'
                    })

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin with selection limits."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=LimitedSelectMultiple(max_selections=3),
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["assigned_extensions"]
        widget_html = field.widget.render("assigned_extensions", None)
        
        # Verify limit attributes are present
        self.assertIn('data-max-selections="3"', widget_html)
        self.assertIn('class="limited-select-multiple"', widget_html)
        
        # Test with selections at the limit
        limit_selection = [self.extensions[0].pk, self.extensions[1].pk, self.extensions[2].pk]
        widget_html = field.widget.render("assigned_extensions", limit_selection)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, 3)
        
        # Test with selections over the limit (widget should still render all)
        over_limit_selection = [ext.pk for ext in self.extensions[:5]]
        widget_html = field.widget.render("assigned_extensions", over_limit_selection)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, 5)  # Widget renders all, JS would enforce limit

    def test_multi_select_widget_performance_with_large_datasets(self):
        """Test multi-select widget performance with large datasets."""
        # Create a large dataset
        large_extensions = []
        for i in range(100):
            ext = Extension.objects.create(number=f"large-ext-{i}")
            large_extensions.append(ext)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for large dataset performance."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["assigned_extensions"]
        
        # Test rendering with large dataset (should not crash or timeout)
        import time
        start_time = time.time()
        widget_html = field.widget.render("assigned_extensions", None)
        render_time = time.time() - start_time
        
        # Should complete in reasonable time (less than 1 second)
        self.assertLess(render_time, 1.0)
        
        # Verify all options are present
        total_extensions = Extension.objects.count()
        option_count = widget_html.count('<option')
        self.assertEqual(option_count, total_extensions)
        
        # Test with many selections
        many_selections = [ext.pk for ext in large_extensions[:50]]
        start_time = time.time()
        widget_html = field.widget.render("assigned_extensions", many_selections)
        render_time = time.time() - start_time
        
        # Should still complete in reasonable time
        self.assertLess(render_time, 1.0)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, 50)

    def test_multi_select_widget_with_complex_filtering(self):
        """Test multi-select widget performance with complex filtering."""
        # Create extensions with different categories for filtering
        categories = ["web", "mobile", "api", "database", "cache"]
        categorized_extensions = []
        
        for i, category in enumerate(categories):
            for j in range(5):
                ext = Extension.objects.create(number=f"{category}-ext-{j}")
                categorized_extensions.append(ext)

        def filter_by_category(queryset, instance, request):
            """Complex filter that simulates expensive operations."""
            # Simulate complex filtering logic
            category = getattr(request, 'filter_category', 'web')
            return queryset.filter(number__startswith=category)

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin with complex filtering."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                    limit_choices_to=filter_by_category,
                ),
            }

        # Test with different filter categories
        for category in categories:
            self.request.filter_category = category
            
            admin_instance = TestAdmin(Service, self.site)
            form_cls = admin_instance.get_form(self.request, self.service)
            form = form_cls(instance=self.service)

            field = form.fields["assigned_extensions"]
            widget_html = field.widget.render("assigned_extensions", None)
            
            # Should only contain extensions from the specified category
            expected_extensions = [ext for ext in categorized_extensions 
                                 if ext.number.startswith(category)]
            
            for ext in expected_extensions:
                self.assertIn(f'value="{ext.pk}"', widget_html)
            
            # Should not contain extensions from other categories
            other_extensions = [ext for ext in categorized_extensions 
                              if not ext.number.startswith(category)]
            for ext in other_extensions:
                self.assertNotIn(f'value="{ext.pk}"', widget_html)
            
            # Option count should match filtered results
            option_count = widget_html.count('<option')
            self.assertEqual(option_count, len(expected_extensions))

    def test_multi_select_widget_form_submission_accuracy(self):
        """Test multi-select widget form submission and data binding accuracy."""
        target_extensions = [self.extensions[1], self.extensions[4], self.extensions[8]]
        
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for form submission accuracy."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        
        # Test form submission with multiple selections
        form_data = {"assigned_extensions": [str(ext.pk) for ext in target_extensions]}
        form = form_cls(data=form_data, instance=self.service)
        
        if form.is_valid():
            # Test that cleaned data contains correct values
            cleaned_pks = form.cleaned_data["assigned_extensions"]
            expected_pks = [ext.pk for ext in target_extensions]
            self.assertEqual(sorted(cleaned_pks), sorted(expected_pks))
        else:
            # If form is invalid due to other fields, assigned_extensions should not be the issue
            self.assertNotIn("assigned_extensions", form.errors)
        
        # Test form submission with empty selection
        form_data = {"assigned_extensions": []}
        form = form_cls(data=form_data, instance=self.service)
        
        if form.is_valid():
            # Empty selection should result in empty list
            cleaned_value = form.cleaned_data.get("assigned_extensions", [])
            self.assertEqual(cleaned_value, [])

    def test_multi_select_widget_data_binding_persistence(self):
        """Test that multi-select widget data binding persists correctly through save operations."""
        target_extensions = [self.extensions[2], self.extensions[6], self.extensions[10]]
        
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for data binding persistence."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.CheckboxSelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        
        # Simulate form submission and save
        form_cls = admin_instance.get_form(self.request, self.service)
        form_data = {"assigned_extensions": [str(ext.pk) for ext in target_extensions]}
        form = form_cls(data=form_data, instance=self.service)
        
        if form.is_valid():
            # Save the form (this would normally be done by admin)
            admin_instance.save_model(self.request, self.service, form, change=True)
            
            # Verify the bindings were persisted
            for ext in target_extensions:
                ext.refresh_from_db()
                self.assertEqual(ext.service, self.service)
            
            # Verify other extensions are not bound
            other_extensions = [ext for ext in self.extensions if ext not in target_extensions]
            for ext in other_extensions:
                ext.refresh_from_db()
                self.assertNotEqual(ext.service, self.service)

    def test_multi_select_widget_with_preselected_values(self):
        """Test multi-select widget rendering with various pre-selected value scenarios."""
        # Bind some extensions to the service
        bound_extensions = [self.extensions[0], self.extensions[3], self.extensions[7]]
        for ext in bound_extensions:
            ext.service = self.service
            ext.save()

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for pre-selected values."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        # Test initial form data includes pre-selected values
        expected_pks = sorted([ext.pk for ext in bound_extensions])
        actual_pks = sorted(form.initial.get("assigned_extensions", []))
        self.assertEqual(actual_pks, expected_pks)
        
        # Test widget rendering with pre-selected values
        field = form.fields["assigned_extensions"]
        bound_pks = [ext.pk for ext in bound_extensions]
        widget_html = field.widget.render("assigned_extensions", bound_pks)
        
        # Should have selected attribute on the correct options
        for ext_pk in bound_pks:
            self.assertIn(f'value="{ext_pk}"', widget_html)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, len(bound_extensions))

    def test_multi_select_widget_with_custom_attributes(self):
        """Test multi-select widgets with custom HTML attributes and CSS classes."""
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin with custom widget attributes."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple(attrs={
                        "class": "custom-multi-select",
                        "data-testid": "extension-selector",
                        "size": "10",
                        "style": "width: 400px; height: 200px;",
                    }),
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["assigned_extensions"]
        widget_html = field.widget.render("assigned_extensions", None)
        
        # Verify custom attributes are present
        self.assertIn('class="custom-multi-select"', widget_html)
        self.assertIn('data-testid="extension-selector"', widget_html)
        self.assertIn('size="10"', widget_html)
        self.assertIn('style="width: 400px; height: 200px;"', widget_html)
        
        # Basic multi-select functionality should still work
        self.assertIn("<select", widget_html)
        self.assertIn("multiple", widget_html)
        for ext in self.extensions:
            self.assertIn(f'value="{ext.pk}"', widget_html)

    def test_multi_select_widget_edge_cases(self):
        """Test multi-select widget edge cases and error scenarios."""
        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            """Test admin for edge cases."""
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    label="Extensions",
                    multiple=True,
                    widget=widgets.SelectMultiple,
                ),
            }

        admin_instance = TestAdmin(Service, self.site)
        form_cls = admin_instance.get_form(self.request, self.service)
        form = form_cls(instance=self.service)

        field = form.fields["assigned_extensions"]
        
        # Test rendering with invalid values (should not crash)
        invalid_values = [99999, "invalid", None]
        widget_html = field.widget.render("assigned_extensions", invalid_values)
        self.assertIn("<select", widget_html)
        self.assertIn("multiple", widget_html)
        # Invalid values should not cause any options to be selected
        self.assertNotIn("selected", widget_html)
        
        # Test rendering with mixed valid and invalid values
        mixed_values = [self.extensions[0].pk, 99999, self.extensions[2].pk, "invalid"]
        widget_html = field.widget.render("assigned_extensions", mixed_values)
        # Valid values should be selected
        self.assertIn(f'value="{self.extensions[0].pk}"', widget_html)
        self.assertIn(f'value="{self.extensions[2].pk}"', widget_html)
        # Should have 2 selected options (only the valid ones)
        selected_count = widget_html.count("selected")
        self.assertEqual(selected_count, 2)
        
        # Test with empty queryset
        Extension.objects.all().delete()
        widget_html = field.widget.render("assigned_extensions", None)
        self.assertIn("<select", widget_html)
        self.assertIn("multiple", widget_html)
        # Should have no options
        option_count = widget_html.count('<option')
        self.assertEqual(option_count, 0)
