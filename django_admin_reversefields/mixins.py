"""Admin mixins for reverse ForeignKey editing.

``ReverseRelationAdminMixin`` injects virtual form fields that operate on
reverse ForeignKey relationships (fields that live on the related model) so
administrators can bind or unbind related objects directly from the parent
model's change form. The mixin coordinates four layers of behaviour:

* Declarative configuration with :class:`ReverseRelationConfig`
* Dynamic form construction with scoped querysets and widgets
* Optional permission gating for rendering and validation
* Transactional synchronization of the underlying ForeignKey rows

The default widgets match Django's admin widgets, but any custom widget can be
provided through configuration. Typical use-cases include assigning a single
related object (single-select) or managing a set of related objects
(multi-select) where the ForeignKey lives on the reverse-side model.

Permissions overview
--------------------

When ``reverse_permissions_enabled`` is True, three permission input shapes are
supported, checked in this precedence order:

1) Per-field ``ReverseRelationConfig.permission``
2) Global ``reverse_permission_policy`` on the admin
3) Fallback to ``request.user.has_perm("{app}.change_{model}")``

Accepted inputs for 1) and 2):

* Function (``PermissionCallable``): ``(request, obj, config, selection) -> bool``
* Policy object (``ReversePermissionPolicy``): callable object, may expose
  ``permission_denied_message``
* Object with only ``has_perm(...)`` method

Gates:

* Render gate (no selection): uses only the global policy (or fallback) to
  hide/disable fields via ``reverse_permission_mode``.
* Validation gate (with selection): evaluates per-field or global policy on the
  actual selection; attaches a field error when denied.
* Persist gate (save): filters the update payload so unauthorized fields are
  ignored even if crafted in POST data.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models, transaction
from django.http import HttpRequest

PermissionCallable = Callable[
    [HttpRequest, models.Model | None, "ReverseRelationConfig", Any | None],
    bool,
]


@dataclass(frozen=True, init=False)
class ReverseRelationConfig:
    """Configuration for a virtual reverse-relation admin field.

    This dataclass describes how a virtual field should be rendered on an admin
    form to manage a reverse ForeignKey relationship. The virtual field does not
    exist on the model; instead, it controls one or more rows on the reverse-side
    model that hold a ForeignKey pointing back to the current object.

    Attributes:
        model (type[models.Model]):
            The reverse-side Django model that holds the ForeignKey.

        fk_field (str):
            The name of the ForeignKey field on the reverse-side model (the one
            specified in ``model``) that points back to the current admin
            object.

        label (str | None):
            Optional human-friendly label for the form field. If omitted, a
            label is derived from ``model._meta.verbose_name`` (or plural when
            ``multiple`` is True).

        help_text (str | None):
            Optional help text displayed with the form field.

        required (bool):
            Whether a selection is required. If True, the form will enforce that
            at least one value is selected (for multi) or a value is present
            (for single).

        multiple (bool):
            If True, a multi-select is rendered and the resulting set of objects
            on the reverse side will be synchronized on save. If False, a
            single-select is rendered and only one object may point to the
            current instance (others will be unbound on save).

        limit_choices_to (Callable | dict | None):
            Either a callable ``(queryset, instance, request) -> queryset`` that
            can apply dynamic, per-request filtering (recommended), or a dict
            used as ``queryset.filter(**dict)`` for static filtering.
            Common usage: include only unbound objects, plus those already bound
            to the current instance.

        widget (forms.Widget | type[forms.Widget] | None):
            Optional widget instance or class to use for rendering. Defaults to
            Django's ``forms.Select`` for single-select and
            ``FilteredSelectMultiple`` for multi-select. You can supply Unfold,
            DAL, or other custom widgets here.

        ordering (Iterable[str] | None):
            Optional ordering to apply to the limited queryset (e.g.,
            ``("displayName",)``).

        clean (Callable[[models.Model, Any, HttpRequest], None] | None):
            Optional per-field validation hook. When provided, it is invoked
            from the derived form's ``clean()`` with
            ``(instance, selection, request)``. Raise ``forms.ValidationError``
            to attach an error to this field and block save; return ``None`` for
            success.

        permission (ReversePermissionPolicy | PermissionCallable | object | None):
            Optional per-field permission policy controlling whether the user
            may modify this virtual field. Supported values include:

            - A callable ``(request, obj, config, selection) -> bool``
            - An object with ``has_perm(request, obj, config, selection) -> bool``
            - An object implementing ``__call__`` following
              :class:`ReversePermissionPolicy`

            Policy objects may expose ``permission_denied_message`` for UI
            feedback during validation.

        permission_denied_message (str | None):
            Optional custom error message attached to the field when a
            selection is denied by permission checks during form validation.

        bulk (bool):
            When True, use Django's .update() method for bind/unbind operations
            instead of individual model saves. This bypasses model signals
            (pre_save, post_save, etc.) but provides better performance for
            large datasets. Defaults to False for backward compatibility.

    Example:
        >>> ReverseRelationConfig(
        ...     model=Site,
        ...     fk_field="meraki",
        ...     label="Site",
        ...     multiple=False,
        ...     ordering=("displayName",),
        ...     limit_choices_to=lambda qs, instance, request: qs.filter(meraki__isnull=True)
        ... )
    """

    def __init__(
        self,
        model: type[models.Model],
        fk_field: str,
        label: str | None = None,
        help_text: str | None = None,
        required: bool = False,
        multiple: bool = False,
        limit_choices_to: (
            Callable[[models.QuerySet, Any, HttpRequest], models.QuerySet] | dict[str, Any] | None
        ) = None,
        widget: forms.Widget | type[forms.Widget] | None = None,
        ordering: Iterable[str] | None = None,
        clean: Callable[[models.Model, Any, HttpRequest], None] | None = None,
        permission: ReversePermissionPolicy | PermissionCallable | object | None = None,
        permission_denied_message: str | None = None,
        bulk: bool = False,
    ) -> None:
        """Initialize ReverseRelationConfig.

        Args:
            model (Type[models.Model]): Reverse-side model holding the FK.
            fk_field (str): Name of the ForeignKey field on the reverse-side
                model (the one specified in ``model``) that points back to the
                current admin object.
            label (Optional[str]): Optional field label. If omitted, a label is
                derived from the reverse model's verbose name.
            help_text (Optional[str]): Optional help text shown under the field.
            required (bool): If True, selection is required (enforced by form).
            multiple (bool): If True, use multi-select and sync many rows.
            limit_choices_to (Optional[Callable|dict]): Callable
                ``(queryset, instance, request) -> queryset`` or a dict used for
                ``queryset.filter(**dict)`` to limit choices (e.g., unbound or
                already-bound-to-current).
            widget (Optional[forms.Widget|type[forms.Widget]]): Widget instance
                or class to render the field. Defaults to Django's ``forms.Select`` for
                single and ``FilteredSelectMultiple`` for multi.
            ordering (Optional[Iterable[str]]): Optional ordering for the
                resulting queryset.
            clean (Optional[Callable[[models.Model, Any, HttpRequest], None]]):
                Optional per-field validation hook invoked from the derived
                ``ModelForm.clean()``. Receives ``(instance, selection, request)``
                and should raise ``forms.ValidationError`` to block submission
                or return ``None`` for success.
            permission (Optional[ReversePermissionPolicy | PermissionCallable | object]):
                Optional per-field permission policy. Accepts callables,
                objects with ``has_perm(...)`` or objects implementing
                :class:`ReversePermissionPolicy`. When provided, the policy
                determines whether the user can modify this field and may
                expose ``permission_denied_message`` for feedback.
            permission_denied_message (Optional[str]): Optional error message
                to display on the field when permission checks fail during
                form validation.
            bulk (bool): When True, use Django's .update() method for
                bind/unbind operations instead of individual model saves.
                This bypasses model signals but provides better performance
                for large datasets. Defaults to False for backward compatibility.

        """
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "fk_field", fk_field)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "help_text", help_text)
        object.__setattr__(self, "required", required)
        object.__setattr__(self, "multiple", multiple)
        object.__setattr__(self, "limit_choices_to", limit_choices_to)
        object.__setattr__(self, "widget", widget)
        object.__setattr__(self, "ordering", ordering)
        object.__setattr__(self, "clean", clean)
        object.__setattr__(self, "permission", permission)
        object.__setattr__(self, "permission_denied_message", permission_denied_message)
        object.__setattr__(self, "bulk", bulk)

    model: type[models.Model]
    fk_field: str
    label: str | None = None
    help_text: str | None = None
    required: bool = False
    multiple: bool = False
    limit_choices_to: (
        Callable[[models.QuerySet, Any, HttpRequest], models.QuerySet] | dict[str, Any] | None
    ) = None
    widget: forms.Widget | type[forms.Widget] | None = None
    ordering: Iterable[str] | None = None
    clean: Callable[[models.Model, Any, HttpRequest], None] | None = None
    permission: ReversePermissionPolicy | PermissionCallable | object | None = None
    permission_denied_message: str | None = None
    bulk: bool = False


class ReversePermissionPolicy(Protocol):
    """Protocol for checking reverse relation modification permissions.

    Policies may be provided as callable objects or as objects exposing a
    ``has_perm`` method. The mixin calls ``has_perm`` if present before falling
    back to calling the object itself, so implementations can opt into either
    style. Policy objects may provide ``permission_denied_message`` to customise
    validation errors.

    Example::

        class StaffOnlyPolicy:
            permission_denied_message = "Staff access required"

            def __call__(self, request, obj, config, selection):
                return getattr(request.user, "is_staff", False)
    """

    def __call__(
        self,
        request: HttpRequest,
        obj: models.Model | None,
        config: ReverseRelationConfig,
        selection: Any | None,
    ) -> bool:
        """Check if the user may modify the reverse relation for this field.

        Args:
            request (HttpRequest): Current HTTP request containing user information
                and other request context.
            obj (models.Model | None): The parent model instance being edited.
                May be None for new instances or in certain contexts.
            config (ReverseRelationConfig): Configuration object containing
                field-specific settings and metadata.
            selection (Any | None): Current selection value, if applicable.
                The type depends on the specific field implementation.

        Returns:
            bool: True if the user is allowed to make changes to this reverse
                relation, False otherwise.

        Note:
            When returning False, consider setting permission_denied_message
            to provide helpful feedback to users about why access was denied.
        """

    permission_denied_message: str | None = None
    """Optional error message to display on the field when permission checks fail during
    form validation.

    This message will be shown to users when __call__ returns False, helping them
    understand why they cannot modify the reverse relation.
    """


class ReverseRelationAdminMixin:
    """Mixin to expose reverse ForeignKey bindings on admin forms.

    Add this mixin to a Django admin class and declare one or more virtual
    fields in ``reverse_relations``. Each virtual field renders a form control
    that operates on objects of ``ReverseRelationConfig.model`` by updating its
    ``fk_field`` to point at the current admin instance.

    The mixin ensures:
      - The virtual fields appear in ``fieldsets`` without causing Django to
        raise unknown-field errors during form construction.
      - Querysets are filtered per request/object via ``limit_choices_to`` and
        can be ordered or customised with widgets.
      - Initial selections reflect the current reverse bindings for the object
        under edit.
      - Permission gating (optional) can hide/disable fields at render-time and
        block unauthorized selections during validation.
      - On save, only authorized fields are persisted and the reverse
        ForeignKey(s) are synchronized to match the submitted values
        (unbinding anything deselected).

    Attributes:
        reverse_relations (dict[str, ReverseRelationConfig]):
            Mapping of virtual field name to configuration. The keys here should
            be used inside the admin's ``fieldsets`` like any normal field.

        reverse_relations_atomic (bool):
            When True (default), all reverse relation updates performed during a
            form save are executed inside a single ``transaction.atomic()``
            block. Within each configured field, unbinds are applied before
            binds to reduce transient uniqueness conflicts. Any database error
            will roll back the entire set of updates so no partial state is
            persisted. Set to False to disable transactional behavior.

        reverse_permissions_enabled (bool):
            When True, require permission to modify reverse fields.

        reverse_permission_policy (Optional[ReversePermissionPolicy | object]):
            Optional global policy (callable or object with has_perm) used before the
            default change_<model> check. Per-field config.permission still takes
            precedence over this.

        reverse_permission_mode (str):
            Behavior when user lacks permission on the reverse model for a field:
            - "disable": render field disabled (read-only) and ignore posted changes
            - "hide": remove field from the form

    Usage:
        >>> class MyAdmin(ReverseRelationAdminMixin, ModelAdmin):
        ...     reverse_relations = {
        ...         "site_binding": ReverseRelationConfig(
        ...             model=Site,
        ...             fk_field="meraki",
        ...             ordering=("displayName",),
        ...         )
        ...     }
    """

    reverse_relations: dict[str, ReverseRelationConfig] = {}
    """Mapping of virtual field name to configuration."""

    reverse_relations_atomic: bool = True
    """When True (default), all reverse relation updates performed during a
    form save are executed inside a single ``transaction.atomic()``
    block. Within each configured field, unbinds are applied before
    binds to reduce transient uniqueness conflicts. Any database error
    will roll back the entire set of updates so no partial state is
    persisted. Set to False to disable transactional behavior."""

    reverse_permissions_enabled: bool = False
    """When True, require permission to modify reverse fields."""

    reverse_permission_policy: ReversePermissionPolicy | PermissionCallable | object | None = None
    """Optional global policy (callable or object with ``has_perm``) used before
    the default ``change_<model>`` check. Per-field ``config.permission`` still
    takes precedence over this."""

    reverse_permission_mode: str = "disable"
    """Behavior when user lacks permission on the reverse model for a field:
    - `"disable"`: render field disabled (read-only) and ignore posted changes
    - `"hide"`: remove the field from the form"""

    reverse_render_uses_field_policy: bool = False
    """If True, the render gate consults per-field/global policies via
    :meth:`has_reverse_change_permission` (with ``selection=None``) instead of
    the base permission check. This lets per-field policies affect visibility
    and editability before any selection exists. Default False preserves the
    global/base-only render behaviour."""

    # no alias/back-compat: package did not ship previous flag

    def has_reverse_change_permission(
        self,
        request: HttpRequest,
        obj: models.Model | None,
        config: ReverseRelationConfig,
        selection: Any = None,
    ) -> bool:
        """Check if the user may change the reverse model for this field.

        By default, requires the global ``change`` permission on the reverse
        model. Overrides evaluate in order of precedence: per-field policies on
        ``ReverseRelationConfig.permission``, then
        ``reverse_permission_policy`` on the admin, followed by this fallback
        method. Override to enforce object-level checks or alternative
        permission codenames.

        Args:
            request (HttpRequest): Current request (for ``user``).
            obj (models.Model | None): The parent instance being edited.
            config (ReverseRelationConfig): Field configuration.
            selection (Any): Current selection, if applicable.

        Returns:
            bool: True if changes are allowed.
        """
        # 1) Per-field policy supplied on the config
        policy = getattr(config, "permission", None)
        if policy is not None:
            if hasattr(policy, "has_perm"):
                return bool(policy.has_perm(request, obj, config, selection))
            if callable(policy):
                return bool(policy(request, obj, config, selection))

        # 2) Global policy on the admin, if supplied
        policy = getattr(self, "reverse_permission_policy", None)
        if policy is not None:
            if hasattr(policy, "has_perm"):
                return bool(policy.has_perm(request, obj, config, selection))
            if callable(policy):
                return bool(policy(request, obj, config, selection))

        # 3) Default global change permission on the reverse model
        app_label = config.model._meta.app_label
        model_name = config.model._meta.model_name
        return bool(
            getattr(request, "user", None)
            and request.user.has_perm(f"{app_label}.change_{model_name}")
        )

    def _has_base_permission(
        self,
        request: HttpRequest,
        obj: models.Model | None,
        config: ReverseRelationConfig,
    ) -> bool:
        """Base permission for the render gate (no selection context).

        The render gate decides whether a field is visible or disabled before
        any selection is available. Selection-dependent policies are evaluated
        later during form ``clean()``. When a global policy is provided it is
        consulted here; otherwise the default ``change_<model>`` permission is
        used. If ``request.user`` is missing or lacks ``has_perm`` the field is
        rendered (admin view-level guards are assumed to apply).
        """
        policy = getattr(self, "reverse_permission_policy", None)
        if policy is not None:
            if hasattr(policy, "has_perm"):
                return bool(policy.has_perm(request, obj, config, None))
            if callable(policy):
                return bool(policy(request, obj, config, None))
        user = getattr(request, "user", None)
        if not hasattr(user, "has_perm"):
            return True
        app = config.model._meta.app_label
        model = config.model._meta.model_name
        return bool(user.has_perm(f"{app}.change_{model}"))

    def get_reverse_relations(self) -> dict[str, ReverseRelationConfig]:
        """Return the configured reverse relations for this admin.

        Returns:
            dict[str, ReverseRelationConfig]: Mapping of virtual field names to
            their configuration.
        """
        return self.reverse_relations

    def get_fields(self, request, obj=None):  # type: ignore[override]
        """Ensure virtual reverse field names are part of the rendered fields.

        When an admin does not declare ``fieldsets`` (and does not supply
        ``fields`` explicitly), Django renders all form fields returned by
        ``get_fields``. This override appends the virtual reverse field names so
        templates include them. The base ``get_form`` implementation receives
        the same list and our ``get_form`` override will strip virtual names
        before building the base form to avoid unknown-field errors.
        """
        base_fields = super().get_fields(request, obj)
        relations = tuple(self.get_reverse_relations().keys())
        if not relations:
            return base_fields
        merged = list(base_fields or [])
        for name in relations:
            if name not in merged:
                merged.append(name)
        return merged

    def get_form(self, request: HttpRequest, obj=None, **kwargs):
        """Create a ModelForm class with injected reverse-relation fields.

        This method filters out the virtual reverse field names from the
        ``fields`` argument (which Django constructs from ``fieldsets``), then
        delegates to the parent ``get_form``. After the base form class is
        created, it dynamically injects the reverse fields and wires up their
        querysets and initial values.

        Args:
            request (HttpRequest): The current request.
            obj (models.Model | None): The instance being edited, if any.
            **kwargs: Additional arguments passed to the base implementation.

        Returns:
            type[forms.ModelForm]: A dynamically derived form class containing
            the configured reverse relation fields.
        """
        relations = dict(self.get_reverse_relations())
        if relations:
            provided_fields = kwargs.get("fields")
            if provided_fields:
                filtered_fields = tuple(
                    fname for fname in provided_fields if fname not in relations
                )
                if filtered_fields != tuple(provided_fields):
                    kwargs = {**kwargs, "fields": filtered_fields}
            else:
                # Derive fields from fieldsets (if provided) and strip virtual names.
                try:
                    fieldsets = self.get_fieldsets(request, obj)
                except Exception:
                    fieldsets = None
                if fieldsets:

                    def _flatten(items):
                        flat = []
                        for item in items:
                            if isinstance(item, (list, tuple)):
                                flat.extend(_flatten(item))
                            else:
                                flat.append(item)
                        return flat

                    declared = []
                    for _name, opts in fieldsets:
                        fields = opts.get("fields") or ()
                        declared.extend(
                            _flatten(fields if isinstance(fields, (list, tuple)) else (fields,))
                        )
                    filtered_fields = tuple(f for f in declared if f and f not in relations)
                    kwargs = {**kwargs, "fields": filtered_fields}

        # No early raises. Rendering gate handles visibility/editability.

        form_class = super().get_form(request, obj, **kwargs)
        if not relations:
            return form_class

        admin_instance = self
        base_fields = form_class.base_fields.copy()
        declared_fields = getattr(form_class, "declared_fields", {}).copy()

        for field_name, config in relations.items():
            field = admin_instance._build_reverse_field(config, obj, request, defer_queryset=True)
            base_fields[field_name] = field
            declared_fields[field_name] = field

        attrs = {
            "__module__": form_class.__module__,
            "base_fields": base_fields,
            "declared_fields": declared_fields,
            "_reverse_relation_configs": relations,
        }

        ReverseRelationForm = type(
            f"{form_class.__name__}ReverseRelations",
            (form_class,),
            attrs,
        )

        base_init = form_class.__init__
        base_clean = getattr(form_class, "clean", None)

        def __init__(self, *args, **form_kwargs):
            base_init(self, *args, **form_kwargs)
            self._reverse_relation_data = None
            instance = getattr(self, "instance", None)
            for field_name, config in relations.items():
                if field_name not in self.fields:
                    self.fields[field_name] = admin_instance._build_reverse_field(
                        config, instance, request, defer_queryset=True
                    )
                field = self.fields[field_name]
                queryset = admin_instance._get_reverse_queryset(config, instance, request)
                field.queryset = queryset
                initial = admin_instance._get_reverse_initial(config, instance)
                if initial is not None:
                    self.initial[field_name] = initial

            # Render gate: enforce base permissions per reverse field (no selection yet)
            perms: dict[str, bool] = {}
            if admin_instance.reverse_permissions_enabled:
                for field_name, config in list(relations.items()):
                    if getattr(admin_instance, "reverse_render_uses_field_policy", False):
                        allowed = admin_instance.has_reverse_change_permission(
                            request, instance, config, None
                        )
                    else:
                        allowed = admin_instance._has_base_permission(request, instance, config)
                    perms[field_name] = allowed
                    if not allowed:
                        mode = admin_instance.reverse_permission_mode
                        if mode == "hide":
                            if field_name in self.fields:
                                self.fields.pop(field_name, None)
                        else:  # disable mode
                            if field_name in self.fields:
                                f = self.fields[field_name]
                                f.disabled = True
                                f.required = False
            self._reverse_relation_perms = perms

        ReverseRelationForm.__init__ = __init__

        def clean(self):
            """Run built-in validation plus reverse-field hooks and permissions."""
            if base_clean:
                cleaned = base_clean(self)
            else:
                cleaned = forms.ModelForm.clean(self)
            # Run per-field hooks, attaching errors to their respective fields.
            for field_name, cfg in relations.items():
                if getattr(cfg, "clean", None):
                    try:
                        cfg.clean(self.instance, self.cleaned_data.get(field_name), request)
                    except forms.ValidationError as exc:  # type: ignore[reportGeneralTypeIssues]
                        self.add_error(field_name, exc)
                # Permission validation that depends on the selection: if
                # enforcement is enabled and policy denies this specific
                # selection, attach a field error to inform the user. Save will
                # still guard against unauthorized updates as a second line.
                if admin_instance.reverse_permissions_enabled and field_name in self.cleaned_data:
                    # Do not attach errors for hidden/disabled fields; UI already enforces
                    if field_name not in self.fields or getattr(
                        self.fields[field_name], "disabled", False
                    ):
                        continue
                    selection = self.cleaned_data.get(field_name)
                    allowed = admin_instance.has_reverse_change_permission(
                        request, getattr(self, "instance", None), cfg, selection
                    )
                    if not allowed:
                        # Only add a field error when a custom policy is involved
                        if (
                            getattr(cfg, "permission", None) is not None
                            or getattr(admin_instance, "reverse_permission_policy", None)
                            is not None
                        ):
                            # Prefer field override, then per-field policy object's message,
                            # then global policy object's message, then default.
                            field_policy = getattr(cfg, "permission", None)
                            global_policy = getattr(
                                admin_instance, "reverse_permission_policy", None
                            )
                            message = (
                                getattr(cfg, "permission_denied_message", None)
                                or getattr(field_policy, "permission_denied_message", None)
                                or getattr(global_policy, "permission_denied_message", None)
                                or "You do not have permission to choose this value."
                            )
                            self.add_error(field_name, forms.ValidationError(message))
            return cleaned

        ReverseRelationForm.clean = clean

        base_save = form_class.save

        def save(self, commit=True):
            """Persist form data and synchronize reverse relations.

            Args:
                commit (bool): Whether to commit immediately. If False, the
                    reverse relation payload is stored and applied in
                    ``save_model``.

            Returns:
                models.Model: The saved instance.
            """
            instance = base_save(self, commit)

            # Exclude unauthorized fields from the update payload to avoid
            # persisting changes from crafted POSTs.
            def _is_allowed(name: str) -> bool:
                if not admin_instance.reverse_permissions_enabled:
                    return True
                cfg = relations[name]
                selection = self.cleaned_data.get(name)
                return admin_instance.has_reverse_change_permission(
                    request, instance, cfg, selection
                )

            allowed_fields = [name for name in relations if _is_allowed(name)]
            payload = {
                field_name: self.cleaned_data.get(field_name)
                for field_name in allowed_fields
                if field_name in self.cleaned_data
            }
            if commit:
                admin_instance._apply_reverse_relations(instance, payload)
                self._reverse_relation_data = None
            else:
                self._reverse_relation_data = payload
            return instance

        ReverseRelationForm.save = save

        return ReverseRelationForm

    def save_model(self, request: HttpRequest, obj, form, change):
        """Save model and apply any deferred reverse relation updates.

        This ensures reverse relations are synchronized even when the form save
        was called with ``commit=False``.

        Args:
            request (HttpRequest): The current request.
            obj (models.Model): The model instance being saved.
            form (forms.ModelForm): The bound form.
            change (bool): True if updating an existing object, False if adding.
        """
        super().save_model(request, obj, form, change)
        if hasattr(form, "_reverse_relation_data") and form._reverse_relation_data is not None:
            self._apply_reverse_relations(obj, form._reverse_relation_data)
            form._reverse_relation_data = None

    def _build_reverse_field(
        self,
        config: ReverseRelationConfig,
        instance,
        request: HttpRequest,
        defer_queryset: bool = False,
    ):
        """Construct a form field for the given reverse relation config.

        Args:
            config (ReverseRelationConfig): The reverse relation configuration.
            instance (models.Model | None): The instance being edited, if any.
            request (HttpRequest): The current request.

        Returns:
            forms.Field: A ``ModelChoiceField`` or ``ModelMultipleChoiceField``
            configured with labels, help text, widget, and a queryset (empty if
            ``defer_queryset`` is True).
        """
        if defer_queryset:
            queryset = config.model._default_manager.none()
        else:
            queryset = self._get_reverse_queryset(config, instance, request)
        label = config.label
        if not label:
            meta = config.model._meta
            label = (
                meta.verbose_name_plural.title() if config.multiple else meta.verbose_name.title()
            )
        widget = self._resolve_widget(config, label, config.multiple)
        if config.multiple:
            return forms.ModelMultipleChoiceField(
                queryset=queryset,
                required=config.required,
                label=label,
                help_text=config.help_text,
                widget=widget,
            )
        field = forms.ModelChoiceField(
            queryset=queryset,
            required=config.required,
            label=label,
            help_text=config.help_text,
            widget=widget,
        )
        field.empty_label = "---------"
        return field

    def _resolve_widget(self, config: ReverseRelationConfig, label: str, multiple: bool):
        """Resolve the widget to use for a reverse relation field.

        If a widget instance or class is provided on the config, it is used. By
        default, multi-select uses Django's ``FilteredSelectMultiple`` and
        single-select uses Django's ``forms.Select``.

        Args:
            config (ReverseRelationConfig): The field configuration.
            label (str): The computed field label (used by some widgets).
            multiple (bool): Whether the field is multi-select.

        Returns:
            forms.Widget: The widget instance to use.
        """
        widget = config.widget
        if widget:
            return widget() if isinstance(widget, type) else widget
        if multiple:
            return FilteredSelectMultiple(label, is_stacked=False)
        return forms.Select()

    def _get_reverse_queryset(self, config: ReverseRelationConfig, instance, request: HttpRequest):
        """Compute the queryset for a reverse relation field.

        Applies ``limit_choices_to`` (callable or dict) and optional ordering.
        This is called during form initialization and can depend on the current
        object and request.

        Args:
            config (ReverseRelationConfig): The field configuration.
            instance (models.Model | None): The instance being edited, if any.
            request (HttpRequest): The current request.

        Returns:
            models.QuerySet: The filtered and ordered queryset.
        """
        queryset = config.model._default_manager.all()
        limiter = config.limit_choices_to
        if callable(limiter):
            queryset = limiter(queryset, instance, request)
        elif limiter:
            queryset = queryset.filter(**limiter)
        if config.ordering:
            queryset = queryset.order_by(*config.ordering)
        return queryset

    def _get_reverse_initial(self, config: ReverseRelationConfig, instance):
        """Compute the initial selection for a reverse relation field.

        Args:
            config (ReverseRelationConfig): The field configuration.
            instance (models.Model | None): The instance being edited, if any.

        Returns:
            list[int] | int | None: For multi-select fields, returns a list of
            primary keys. For single-select fields, returns the primary key of
            the related object or ``None`` if there is no current binding.
        """
        if not instance or not getattr(instance, "pk", None):
            return [] if config.multiple else None
        queryset = config.model._default_manager.filter(**{config.fk_field: instance})
        if config.multiple:
            return list(queryset.values_list("pk", flat=True))
        related = queryset.first()
        return related.pk if related else None

    def _apply_bulk_unbind(self, config: ReverseRelationConfig, instance, exclude_pks: set):
        """Unbind multiple objects using .update() for performance.

        Uses Django's .update() method to set the foreign key to None for objects
        that should be unbound from the current instance. This bypasses model
        signals but provides better performance for large datasets.

        Args:
            config (ReverseRelationConfig): The field configuration.
            instance (models.Model): The saved model instance serving as the FK target.
            exclude_pks (set): Set of primary keys to exclude from unbinding.

        Raises:
            forms.ValidationError: If database constraints prevent the unbind operation.
            Exception: Any other database error during the bulk update.
        """
        from django import forms
        from django.db import IntegrityError

        try:
            # Build queryset for objects currently bound to this instance
            queryset = config.model._default_manager.filter(**{config.fk_field: instance})

            # Exclude objects that should remain bound (for multi-select scenarios)
            if exclude_pks:
                queryset = queryset.exclude(pk__in=exclude_pks)

            # Perform bulk unbind using .update()
            if queryset.exists():
                queryset.update(**{config.fk_field: None})

        except IntegrityError as e:
            raise forms.ValidationError(
                f"Bulk unbind operation failed for {config.model._meta.verbose_name}: {e}"
            ) from e
        except Exception as e:
            raise forms.ValidationError(
                f"Unexpected error during bulk unbind operation: {e}"
            ) from e

    def _apply_bulk_bind(self, config: ReverseRelationConfig, instance, target_objects):
        """Bind multiple objects using .update() for performance.

        Uses Django's .update() method to set the foreign key to the target instance
        for objects that should be bound. This bypasses model signals but provides
        better performance for large datasets.

        Args:
            config (ReverseRelationConfig): The field configuration.
            instance (models.Model): The saved model instance serving as the FK target.
            target_objects (list): List of objects to bind to the instance.

        Raises:
            forms.ValidationError: If database constraints prevent the bind operation.
            Exception: Any other database error during the bulk update.
        """
        from django import forms
        from django.db import IntegrityError

        if not target_objects:
            return

        try:
            # Get primary keys of objects that need to be bound
            # Always include the selected primary keys. In bulk single-select flows,
            # an earlier unbind uses .update() which does not refresh in-memory
            # objects from the form queryset. Filtering out objects that "already"
            # point at instance based on stale in-memory attributes would cause a
            # silent unbind when submitting the same selection.
            target_pks = [obj.pk for obj in target_objects]

            # Perform bulk bind using .update() if there are objects to bind
            if target_pks:
                config.model._default_manager.filter(pk__in=target_pks).update(
                    **{config.fk_field: instance}
                )

        except IntegrityError as e:
            raise forms.ValidationError(
                f"Bulk bind operation failed for {config.model._meta.verbose_name}: {e}"
            ) from e
        except Exception as e:
            raise forms.ValidationError(f"Unexpected error during bulk bind operation: {e}") from e

    def _apply_bulk_operations(self, config: ReverseRelationConfig, instance, selection):
        """Coordinate bulk unbind and bind operations for a reverse relation field.

        Maintains the unbind-before-bind ordering to minimize transient constraint
        violations. Handles both single-select and multi-select scenarios using
        bulk .update() operations for better performance.

        Args:
            config (ReverseRelationConfig): The field configuration.
            instance (models.Model): The saved model instance serving as the FK target.
            selection: The submitted selection (object for single-select,
                      iterable of objects for multi-select).

        Raises:
            forms.ValidationError: If database constraints prevent the operations
                                 or other errors occur during bulk updates.
        """
        from django import forms

        try:
            if config.multiple:
                # Multi-select scenario
                selected = list(selection) if selection else []
                selected_ids = {obj.pk for obj in selected}

                # Step 1: Bulk unbind objects that are no longer selected
                # (exclude the ones that should remain bound)
                self._apply_bulk_unbind(config, instance, selected_ids)

                # Step 2: Bulk bind newly selected objects
                self._apply_bulk_bind(config, instance, selected)

            else:
                # Single-select scenario
                target = selection

                # Step 1: Bulk unbind all current relations
                # For single-select, we unbind everything first
                self._apply_bulk_unbind(config, instance, set())

                # Step 2: Bulk bind the target (if provided)
                if target:
                    self._apply_bulk_bind(config, instance, [target])

        except forms.ValidationError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors in ValidationError with meaningful message
            raise forms.ValidationError(
                f"Bulk operation failed for {config.model._meta.verbose_name}: {e}"
            ) from e

    def _apply_individual_operations(self, config: ReverseRelationConfig, instance, selection):
        """Apply bind/unbind operations using individual model saves.

        This is the original behavior that triggers model signals (pre_save, post_save)
        for each object. Used when config.bulk=False or for backward compatibility.

        Args:
            config (ReverseRelationConfig): The field configuration.
            instance (models.Model): The saved model instance serving as the FK target.
            selection: The submitted selection (object for single-select,
                      iterable of objects for multi-select).
        """
        manager = config.model._default_manager
        current = list(manager.filter(**{config.fk_field: instance}))

        if config.multiple:
            selected = list(selection) if selection else []
            selected_ids = {obj.pk for obj in selected}
            # Unbind removed relations first
            for item in current:
                if item.pk not in selected_ids:
                    setattr(item, config.fk_field, None)
                    item.save(update_fields=[config.fk_field])
            # Then bind newly selected relations
            for obj in selected:
                if getattr(obj, config.fk_field) != instance:
                    setattr(obj, config.fk_field, instance)
                    obj.save(update_fields=[config.fk_field])
        else:
            target = selection
            # Unbind all others first
            for item in current:
                if not target or item.pk != getattr(target, "pk", None):
                    setattr(item, config.fk_field, None)
                    item.save(update_fields=[config.fk_field])
            # Then bind the target (if provided)
            if target and getattr(target, config.fk_field) != instance:
                setattr(target, config.fk_field, instance)
                target.save(update_fields=[config.fk_field])

    def _apply_reverse_relations(self, instance, payload: dict[str, Any]):
        """Persist authorized reverse-relation selections to the database.

        Synchronizes the reverse-side ForeignKey(s) so they exactly match the
        submitted form values. Callers pass a payload that has already been
        filtered for permission (``save()`` only includes authorized fields).
        Within each configured relation the method unbinds deselected rows
        before binding new selections to minimize transient uniqueness
        conflicts.

        Args:
            instance (models.Model): The saved model instance serving as the FK
                target.
            payload (dict[str, Any]): Mapping of virtual field name to submitted
                selection (object or iterable of objects for multi-select).

        Raises:
            Exception: Any database or integrity error raised during updates is
                not swallowed and will propagate to the admin. When
                :attr:`reverse_relations_atomic` is True, the transaction will
                be rolled back and no changes will be persisted.

        Notes:
            Updates occur inside a single ``transaction.atomic()`` block when
            :attr:`reverse_relations_atomic` is enabled so either all reverse
            relations are synchronized or none are.
        """

        def _apply() -> None:
            """Process each configured reverse field. Routes to bulk operations
            when config.bulk=True, individual operations when config.bulk=False."""
            for field_name, config in self.get_reverse_relations().items():
                if field_name not in payload:
                    # Skip unauthorized fields that were stripped from the payload. When the
                    # field name is absent we must not touch the existing bindings.
                    continue
                selection = payload.get(field_name)

                if config.bulk:
                    # Route to bulk operations for better performance
                    self._apply_bulk_operations(config, instance, selection)
                else:
                    # Use individual saves (existing behavior)
                    self._apply_individual_operations(config, instance, selection)

        if self.reverse_relations_atomic:
            # Apply all updates as a single unit; on error, the entire set of
            # operations is rolled back so that no partial state is persisted.
            with transaction.atomic():
                _apply()
        else:
            _apply()
