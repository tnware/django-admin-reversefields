Configuration
=============

This guide covers how to control the behaviour of your
:term:`virtual fields <Virtual Field>`: visibility, editability, queryset
scoping, widgets, and permission enforcement. For how these fit into the form
lifecycle, see :doc:`concepts`. For ready-to-run examples, see :doc:`recipes`.

.. contents:: Page contents
   :depth: 2
   :local:

.. _configuration-visibility:

Rendering & visibility
----------------------

How virtual fields appear
^^^^^^^^^^^^^^^^^^^^^^^^^

- ``get_fields``: The mixin appends the virtual names declared in
  :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_relations` to the
  list of fields returned by ``ModelAdmin.get_fields`` so templates know about them.
- ``get_form``: It strips those names from the base ``fields`` passed to the form factory
  (to avoid unknown-field errors), then injects real
  :class:`~django.forms.ModelChoiceField` /
  :class:`~django.forms.ModelMultipleChoiceField` instances with the configured
  label, help text, widget, queryset, and initial selection.

Layout rules (fields vs. fieldsets)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- If you declare ``fieldsets`` or ``fields``, you must include the virtual names
  there (e.g. ``"department_binding"``) or the admin template will not render
  them.
- If neither is declared, Django renders all form fields by default and the
  injected virtual fields appear automatically.
- If you override ``get_fields`` without calling ``super()``, or you return a
  hard-coded ``fields`` list that omits the virtual names, the form will still
  contain the injected fields but the template will not render them.

Visibility vs. editability
^^^^^^^^^^^^^^^^^^^^^^^^^^

When :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_permissions_enabled`
is True the mixin runs a render gate for each virtual field:

- Mode is controlled by :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_permission_mode`:

  - ``"hide"`` removes the field from the form (no input is rendered).
  - ``"disable"`` keeps it visible but sets ``disabled=True`` and relaxes ``required`` to avoid
    spurious "This field is required." errors.
- By default, the render gate consults a base/global permission (roughly
  ``change_<reverse_model>``). To let per-field/global policies decide visibility
  up front, set
  :attr:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.reverse_render_uses_field_policy`
  to True. In that mode
  :meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.has_reverse_change_permission`
  is called with ``selection=None``.

Troubleshooting
^^^^^^^^^^^^^^^

- **Field does not render** — Ensure its virtual name appears in ``fieldsets`` or
  ``fields`` (or do not declare either), and avoid overriding ``get_fields``
  without calling ``super()``.
- **Field renders but is read-only** — Check ``reverse_permissions_enabled`` +
  ``reverse_permission_mode``, and whether ``reverse_render_uses_field_policy``
  is True with a policy that denies access for the current user.

.. _configuration-querysets:

Querysets & widgets
-------------------

Scoping choices
^^^^^^^^^^^^^^^

``ReverseRelationConfig.limit_choices_to`` accepts either a ``dict`` (mirroring
Django's ``ModelAdmin`` behaviour) or a callable of the form
``(queryset, instance, request) -> queryset``. Callables let you combine
request-aware filtering with inclusion of already-related rows, ensuring users
can keep existing :term:`bindings <Binding>` even when a global filter would hide them.

.. caution:: Static dict vs callable

   A static ``dict`` filter cannot "reach back" to include objects already bound
   to the current instance unless they also match the dict. If you need the
   common pattern "unbound or currently bound", prefer a callable, for example::

      from django.db.models import Q

      def unbound_or_current(qs, instance, request):
          if instance and instance.pk:
              return qs.filter(Q(company__isnull=True) | Q(company=instance))
          return qs.filter(company__isnull=True)

Empty querysets
^^^^^^^^^^^^^^^

When the limiter produces an empty queryset, the field renders with no choices.
Form submissions with an empty selection remain valid unless you set
``required=True`` on the :class:`~django_admin_reversefields.mixins.ReverseRelationConfig`.

Ordering selections
^^^^^^^^^^^^^^^^^^^

Apply ``ReverseRelationConfig.ordering`` to control how the queryset is sorted
before rendering. The tuple mirrors Django's ``QuerySet.order_by`` parameters and
runs after ``limit_choices_to`` so you can safely rely on any additional filters
applied there.

Custom widgets
^^^^^^^^^^^^^^

Every :term:`virtual field <Virtual Field>` can override the default widget via
``ReverseRelationConfig.widget``. Supply either a widget instance or a widget
class. This works for stock Django form widgets as well as third-party options
such as Unfold Select2 or Django Autocomplete Light.

.. seealso::
   :doc:`advanced` — Complete DAL/Unfold widget examples.

.. _configuration-permissions:

Permissions
-----------

Use this section to enforce Django permissions on reverse relations and craft
custom :term:`policies <Policy>` beyond the default ``change`` checks. Ready-to-run snippets live
in :ref:`recipe-permissions`.

Permission modes
^^^^^^^^^^^^^^^^

Set ``reverse_permissions_enabled=True`` to have the mixin evaluate access
before rendering or saving a :term:`virtual field <Virtual Field>`. ``reverse_permission_mode`` controls
how denied access surfaces:

* ``"disable"`` (default) — render the field disabled and ignore submitted
  changes. The mixin also sets ``required=False`` on disabled reverse fields so
  that forms do not raise "This field is required." when no initial value is
  present and the browser omits the disabled input from POST data.
* ``"hide"`` — omit the field entirely.

.. note::
   ``hide`` removes the input, so any ``required=True`` on the :term:`virtual field <Virtual Field>`
   does not apply. Use ``disable`` if you need the field to remain visible/read-only
   while relaxing required semantics.

Use standard admin view guards if you want to block the whole page instead of a
single field.

Render-time policies
^^^^^^^^^^^^^^^^^^^^

By default, the render gate only consults a base/global permission to decide
visibility and editability. To let per-field (or global) :term:`policies <Policy>` influence
visibility at render time, set the class flag
``reverse_render_uses_field_policy = True``. In this mode the render gate calls
``has_reverse_change_permission(request, obj, config, selection=None)``. :term:`Policies <Policy>`
must therefore handle ``selection=None`` sensibly.

Example::

   class CompanyAdmin(ReverseRelationAdminMixin, admin.ModelAdmin):
       reverse_permissions_enabled = True
       reverse_render_uses_field_policy = True
       reverse_relations = {
           "department_binding": ReverseRelationConfig(
               model=Department,
               fk_field="company",
               multiple=False,
               permission=lambda request, obj, config, selection: getattr(request.user, "is_staff", False),
           )
       }

The per-field :term:`policy <Policy>` above is evaluated during render with ``selection=None``. If it
returns ``False``, the field will be hidden or disabled according to
``reverse_permission_mode``.

Custom policies
^^^^^^^^^^^^^^^

Permissions can be supplied globally via
:meth:`~django_admin_reversefields.mixins.ReverseRelationAdminMixin.has_reverse_change_permission`
or per field via ``ReverseRelationConfig.permission``. You may provide :term:`policies <Policy>`
in three ergonomic shapes with identical semantics (return ``True`` to allow,
``False`` to deny).

.. tab-set::

   .. tab-item:: Callable

      A callable with the signature ``(request, obj, config, selection) -> bool``
      is ideal for tiny, stateless predicates.

   .. tab-item:: Policy object

      A :term:`Policy <Policy>` object implementing ``__call__`` and optionally
      ``permission_denied_message`` is useful for bundling state or reusable
      messages.

   .. tab-item:: has_perm object

      An object exposing ``has_perm(request, obj, config, selection) -> bool``
      is useful when adapting existing helpers. The ``permission_denied_message``
      attribute is honoured if present.

Per-field :term:`policies <Policy>` override the global method when provided.

Evaluation flow
^^^^^^^^^^^^^^^

Permission checks run at three points:

1. **Render gate** — decides whether a field is hidden or disabled before
   templates render. By default, it checks a base permission. If
   ``reverse_render_uses_field_policy`` is ``True``, it consults the full
   per-field or global :term:`policy <Policy>` (with ``selection=None``).
2. **Validation gate** — once a selection exists, the per-field :term:`policy <Policy>` runs (if
   defined) and otherwise the global :term:`policy <Policy>` is invoked. Denials raise a field
   error using the precedence below. If no custom policy is configured at all
   (neither per-field nor global), the mixin does not attach validation errors
   for base permission denials; instead, the UI gating (``hide``/``disable``)
   applies, and hidden/disabled inputs are ignored on save.
3. **Persistence gate** — as a safety net, the mixin excludes unauthorized
   fields from the update payload so crafted POSTs cannot persist changes.
   This includes hidden and disabled reverse fields.

Error message precedence
^^^^^^^^^^^^^^^^^^^^^^^^

When a :term:`policy <Policy>` denies a selection, the field error message resolves in this
order:

1. ``ReverseRelationConfig.permission_denied_message``
2. ``permission.permission_denied_message`` on the per-field :term:`policy <Policy>` object
3. ``reverse_permission_policy.permission_denied_message`` on the global :term:`policy <Policy>`
   object
4. Default ``"You do not have permission to choose this value."``

.. list-table:: Permission denied message precedence
   :header-rows: 1

   * - Source
     - Example attribute path
     - Precedence
   * - Field override
     - ``config.permission_denied_message``
     - 1 (highest)
   * - Per-field :term:`policy <Policy>` object
     - ``config.permission.permission_denied_message``
     - 2
   * - Global :term:`policy <Policy>` object
     - ``admin.reverse_permission_policy.permission_denied_message``
     - 3
   * - Built-in default
     - ``"You do not have permission to choose this value."``
     - 4 (lowest)

Visualising the flow
^^^^^^^^^^^^^^^^^^^^

.. mermaid::

   flowchart TD
     subgraph Render
       A[Start] --> B{reverse_permissions_enabled?};
       B -- No --> RenderNormal[Render normally];
       B -- Yes --> RenderGate{Render gate};
       RenderGate --> CheckPolicyMode{reverse_render_uses_field_policy?};
       CheckPolicyMode -- Yes --> CheckFieldPolicy{has_reverse_change_permission?};
       CheckPolicyMode -- No --> CheckBasePerms{_has_base_permission?};
       CheckFieldPolicy -- Deny --> SetVisibility;
       CheckBasePerms -- Deny --> SetVisibility{Mode?};
       SetVisibility -- hide --> Hide[Hide field];
       SetVisibility -- disable --> Disable[Disable field];
       CheckFieldPolicy -- Allow --> Visible[Visible/editable];
       CheckBasePerms -- Allow --> Visible;
     end

     subgraph Validate and Persist
       RenderNormal --> Clean;
       Hide --> Clean;
       Disable --> Clean;
       Visible --> Clean[clean: run cfg.clean if present];
       Clean --> Validate{has_reverse_change_permission?};
       Validate -- Deny --> AddError[Add field error];
       Validate -- Allow --> OK;
       AddError --> Persist;
       OK --> Persist[Persistence gate];
       Persist --> FilterPayload[Build payload only for allowed fields];
       FilterPayload --> Save[save: transaction.atomic; unbind before bind];
     end

Minimal examples
^^^^^^^^^^^^^^^^

.. tab-set::

   .. tab-item:: Function (simple rule)

      .. code-block:: python

         def only_staff(request, obj, config, selection):
             return getattr(request.user, "is_staff", False)

         ReverseRelationConfig(..., permission=only_staff)

   .. tab-item:: Policy object (stateful + message)

      .. code-block:: python

         class OrgPolicy:
             def __init__(self, org_id: int):
                 self.org_id = org_id
             permission_denied_message = "You lack access to this organization."
             def __call__(self, request, obj, config, selection):
                 return getattr(request.user, "org_id", None) == self.org_id

         ReverseRelationConfig(..., permission=OrgPolicy(org_id=42))

   .. tab-item:: has_perm object (adapter)

      .. code-block:: python

         class CanBindAdapter:
             permission_denied_message = "Not allowed to bind this item."
             def has_perm(self, request, obj, config, selection):
                 # delegate to some legacy checker
                 return legacy_can_bind(request.user, selection)

         ReverseRelationConfig(..., permission=CanBindAdapter())

.. seealso::
   - :doc:`recipes` — End-to-end permission setups in context.
   - :doc:`concepts` — Where permissions fit in the lifecycle.
