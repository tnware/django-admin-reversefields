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

Release
-------

Version is defined in ``django_admin_reversefields/__init__.py``.

.. code-block:: bash

   uv build
   # or: python -m build
   twine upload dist/*
