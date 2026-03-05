Development
===========

Install (uv)
------------

.. code-block:: bash

   git clone https://github.com/tnware/django-admin-reversefields
   cd django-admin-reversefields
   uv venv .venv
   # Windows PowerShell
   . .\.venv\Scripts\Activate.ps1
   # macOS/Linux
   # source .venv/bin/activate

   uv pip install -e .
   uv pip install -r docs/requirements.txt

Build docs
----------

.. code-block:: bash

   uv run sphinx-build -b html docs docs/_build/html -W

Run tests
---------

.. code-block:: bash

   uv run python manage.py test -v 2

Interactive dev server
----------------------

The ``tests/`` app doubles as a runnable Django instance with realistic models
and admin configs that use the mixin. This is useful for manual smoke-testing
and visual inspection of widgets, permissions, and field rendering.

.. code-block:: bash

   # Use a file-backed database (tests default to :memory:)
   export DJANGO_DB_NAME=db.sqlite3   # Linux/macOS
   # $env:DJANGO_DB_NAME="db.sqlite3"  # Windows PowerShell

   uv run python manage.py migrate
   uv run python manage.py seed      # creates sample data + admin/admin superuser
   uv run python manage.py runserver

Visit ``http://localhost:8000/admin/`` and log in with ``admin`` / ``admin``.

The ``seed`` command creates companies, departments, projects, employees, and
company settings — a mix of bound and unbound objects so you can immediately
test binding and unbinding. It is idempotent and skips if data already exists.

The test models registered in the admin include:

- **Company** — multi-select ``departments`` and ``projects`` virtual fields,
  plus single-select ``settings``
- **Department** — multi-select ``employees`` virtual field

The interactive admin examples use an ``unbound_or_current`` queryset pattern
for reverse fields so users can choose objects that are either unassigned or
already assigned to the object being edited.
Those reverse fields also include ``help_text`` in the admin UI to explain why
some options are intentionally filtered out.

Edit a company to see the mixin in action. The ``db.sqlite3`` file is
git-ignored.

Release
-------

Version is defined in ``pyproject.toml``.

.. code-block:: bash

   uv build
   # or: python -m build
   twine upload dist/*
