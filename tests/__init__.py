from __future__ import annotations

import os

import django
from django.apps import apps

if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"

if not apps.ready:
    django.setup()
