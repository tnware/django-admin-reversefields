"""Test suite for transactional behavior with bulk operations."""

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


class BulkOperationTransactionalTests(BaseAdminMixinTestCase):
    """Test suite for transactional behavior with bulk operations."""

    def test_bulk_operations_respect_reverse_relations_atomic_true(self):
        """Test that bulk operations respect reverse_relations_atomic=True."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations_atomic = True  # Enable atomic transactions
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

        # Mock transaction.atomic to verify it's called
        with mock.patch('django.db.transaction.atomic') as mock_atomic:
            # Configure the mock to act as a context manager
            mock_atomic.return_value.__enter__ = mock.Mock()
            mock_atomic.return_value.__exit__ = mock.Mock(return_value=None)

            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk, ext_2.pk],
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that transaction.atomic was called when reverse_relations_atomic=True
            mock_atomic.assert_called_once()

    def test_bulk_operations_respect_reverse_relations_atomic_false(self):
        """Test that bulk operations respect reverse_relations_atomic=False."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations_atomic = False  # Disable atomic transactions
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

        # Mock transaction.atomic to verify it's NOT called
        with mock.patch('django.db.transaction.atomic') as mock_atomic:
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk, ext_2.pk],
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())
            form.save()

            # Verify that transaction.atomic was NOT called when reverse_relations_atomic=False
            mock_atomic.assert_not_called()

    def test_bulk_operations_rollback_on_failure_with_atomic_true(self):
        """Test that bulk operations rollback properly when they fail with atomic=True."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations_atomic = True  # Enable atomic transactions
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

        # Create test data
        ext_1 = Extension.objects.create(number="1001")
        ext_2 = Extension.objects.create(number="1002")
        site_a = Site.objects.create(name="Site A")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Mock the second bulk operation to fail, simulating a mid-transaction error
        call_count = {'count': 0}
        original_apply_bulk_operations = admin_inst._apply_bulk_operations

        def failing_bulk_operations(config, instance, selection):
            call_count['count'] += 1
            if call_count['count'] == 2:  # Fail on second operation
                raise IntegrityError("Simulated failure in second operation")
            return original_apply_bulk_operations(config, instance, selection)

        with mock.patch.object(
            admin_inst, '_apply_bulk_operations', side_effect=failing_bulk_operations
        ):
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk, ext_2.pk],
                    "site_binding": site_a.pk,
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())

            # Should raise IntegrityError due to the simulated failure
            with self.assertRaises(IntegrityError):
                form.save()

            # Verify that no changes persisted due to rollback
            # Extensions should not be bound to the service
            self.assertEqual(Extension.objects.filter(service=self.service).count(), 0)
            # Site should not be bound to the service
            self.assertIsNone(Site.objects.get(pk=site_a.pk).service)

    def test_bulk_operations_maintain_data_integrity_during_operations(self):
        """Test that bulk operations maintain data integrity during the operation sequence."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations_atomic = True  # Enable atomic transactions
            reverse_relations = {
                "assigned_extensions": ReverseRelationConfig(
                    model=Extension,
                    fk_field="service",
                    multiple=True,
                    bulk=True,
                )
            }

        # Create existing extensions bound to the service
        existing_ext_1 = Extension.objects.create(number="1001", service=self.service)
        existing_ext_2 = Extension.objects.create(number="1002", service=self.service)

        # Create new extensions to bind
        new_ext_1 = Extension.objects.create(number="1003")
        new_ext_2 = Extension.objects.create(number="1004")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        # Track the sequence of operations to verify unbind-before-bind ordering
        operation_sequence = []

        original_apply_bulk_unbind = admin_inst._apply_bulk_unbind
        original_apply_bulk_bind = admin_inst._apply_bulk_bind

        def track_unbind(config, instance, exclude_pks):
            operation_sequence.append(('unbind', exclude_pks))
            return original_apply_bulk_unbind(config, instance, exclude_pks)

        def track_bind(config, instance, target_objects):
            operation_sequence.append(('bind', [obj.pk for obj in target_objects]))
            return original_apply_bulk_bind(config, instance, target_objects)

        with mock.patch.object(admin_inst, '_apply_bulk_unbind', side_effect=track_unbind):
            with mock.patch.object(admin_inst, '_apply_bulk_bind', side_effect=track_bind):
                form = form_cls(
                    {
                        "name": self.service.name,
                        # Select only new extensions, should unbind existing ones
                        "assigned_extensions": [new_ext_1.pk, new_ext_2.pk],
                    },
                    instance=self.service,
                )
                self.assertTrue(form.is_valid())
                form.save()

                # Verify the operation sequence maintains unbind-before-bind ordering
                self.assertEqual(len(operation_sequence), 2)
                self.assertEqual(operation_sequence[0][0], 'unbind')  # First: unbind
                self.assertEqual(operation_sequence[1][0], 'bind')  # Second: bind

                # Verify the correct objects were processed
                unbind_exclude_pks = operation_sequence[0][1]
                bind_pks = operation_sequence[1][1]

                # Unbind should exclude the new extensions (keep them unbound initially)
                self.assertEqual(unbind_exclude_pks, {new_ext_1.pk, new_ext_2.pk})
                # Bind should include the new extensions
                self.assertEqual(set(bind_pks), {new_ext_1.pk, new_ext_2.pk})

        # Verify final state: only new extensions should be bound
        bound_extensions = Extension.objects.filter(service=self.service)
        self.assertEqual(
            set(bound_extensions.values_list('pk', flat=True)), {new_ext_1.pk, new_ext_2.pk}
        )

        # Verify existing extensions were unbound
        self.assertIsNone(Extension.objects.get(pk=existing_ext_1.pk).service)
        self.assertIsNone(Extension.objects.get(pk=existing_ext_2.pk).service)

    def test_bulk_operations_atomic_behavior_with_mixed_configurations(self):
        """Test atomic behavior when mixing bulk and individual operations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations_atomic = True  # Enable atomic transactions
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

        # Mock the individual operations to fail, simulating a mixed failure scenario
        with mock.patch.object(
            admin_inst,
            '_apply_individual_operations',
            side_effect=IntegrityError("Individual operation failed"),
        ):
            form = form_cls(
                {
                    "name": self.service.name,
                    "assigned_extensions": [ext_1.pk, ext_2.pk],  # Bulk operation
                    "site_binding": site_a.pk,  # Individual operation (will fail)
                },
                instance=self.service,
            )
            self.assertTrue(form.is_valid())

            # Should raise IntegrityError due to the individual operation failure
            with self.assertRaises(IntegrityError):
                form.save()

            # Verify that ALL operations were rolled back due to atomic transaction
            # Extensions should not be bound (bulk operation should be rolled back too)
            self.assertEqual(Extension.objects.filter(service=self.service).count(), 0)
            # Site should not be bound
            self.assertIsNone(Site.objects.get(pk=site_a.pk).service)

    def test_bulk_operations_data_integrity_with_constraint_violations(self):
        """Test data integrity when bulk operations encounter constraint violations."""

        class TestAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
            reverse_relations_atomic = True  # Enable atomic transactions
            reverse_relations = {
                "unique_bindings": ReverseRelationConfig(
                    model=UniqueExtension,
                    fk_field="service",
                    multiple=True,  # This will cause constraint violation for OneToOneField
                    bulk=True,
                )
            }

        # Create UniqueExtensions (OneToOneField can only bind one per service)
        unique_1 = UniqueExtension.objects.create(number="1001")
        unique_2 = UniqueExtension.objects.create(number="1002")

        request = self.factory.post("/")
        admin_inst = TestAdmin(Service, self.site)
        form_cls = admin_inst.get_form(request, self.service)

        form = form_cls(
            {
                "name": self.service.name,
                # Trying to bind multiple objects to OneToOneField should fail
                "unique_bindings": [unique_1.pk, unique_2.pk],
            },
            instance=self.service,
        )
        self.assertTrue(form.is_valid())

        # Should raise ValidationError due to constraint violation
        with self.assertRaises(forms.ValidationError) as cm:
            form.save()

        # Verify meaningful error message
        error_message = str(cm.exception)
        self.assertIn("Bulk", error_message)
        self.assertIn("operation failed", error_message)

        # Verify no partial updates persisted (data integrity maintained)
        self.assertIsNone(UniqueExtension.objects.get(pk=unique_1.pk).service)
        self.assertIsNone(UniqueExtension.objects.get(pk=unique_2.pk).service)