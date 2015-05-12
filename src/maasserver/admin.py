# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Register models with Django.

We used to do this directly from `models/__init__.py`, as a side effect of
importing from that package, but it led to `AlreadyRegistered` errors when
running some tests in isolation (even when the import only happened once).

Django automatically discovers the `admin` module and ensures that models are
only registered once.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.contrib import admin
from django.db.models import (
    get_app,
    get_models,
)
from piston.models import Consumer

# Register models in the admin site.  When the DEBUG setting is enabled, the
# webapp will serve an administrator UI at /admin.
admin.site.register(Consumer)
for model in get_models(get_app('maasserver')):
    admin.site.register(model)
