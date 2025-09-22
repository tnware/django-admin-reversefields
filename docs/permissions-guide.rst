Permissions
===========

Use this guide to enforce Django permissions on reverse relations and craft
custom :term:`policies <Policy>` beyond the default ``change`` checks. Ready-to-run snippets live
in :ref:`recipe-permissions`.

.. contents:: Page contents
   :depth: 1
   :local:

Permission modes
----------------

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
--------------------

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
---------------

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
---------------

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
------------------------

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
--------------------

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
----------------

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
   - :doc:`rendering` — Visibility vs editability and the render gate.
   - :doc:`recipes` — End-to-end permission setups in context.
   - :doc:`core-concepts` — Where permissions fit in the lifecycle.
