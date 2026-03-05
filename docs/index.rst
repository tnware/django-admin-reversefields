django-admin-reversefields
==========================

A Django admin mixin that exposes reverse ForeignKey relationships directly on
the parent object's change form. Administrators can bind/unbind related objects
from either side without custom forms or inlines.

* Free software: BSD License
* Homepage: `django-admin-reversefields on GitHub <https://github.com/tnware/django-admin-reversefields>`__
* PyPI: `django-admin-reversefields on PyPI <https://pypi.org/project/django-admin-reversefields/>`__


Core behaviors
--------------

* Declarative config per admin via ``reverse_relations``
* Filters virtual field names before ``ModelForm`` creation to avoid unknown-field errors
* Injects fields dynamically with per-request, per-object querysets and initial values
* On save, synchronizes the real FK(s) on the reverse model(s)

Contents
--------

.. toctree::
   :caption: Getting started
   :maxdepth: 1

   quickstart
   recipes

.. toctree::
   :caption: How it works
   :maxdepth: 1

   concepts

.. toctree::
   :caption: Configuring behavior
   :maxdepth: 1

   configuration
   advanced

.. toctree::
   :caption: Reference
   :maxdepth: 1

   api
   caveats
   glossary

.. toctree::
   :caption: Contributor guide
   :maxdepth: 1

   development
