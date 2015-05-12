# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: run the server.  Overrides the default implementation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = ['Command']

from optparse import make_option
from SocketServer import ThreadingMixIn

from django.core.management.commands.runserver import BaseRunserverCommand
from django.core.servers import basehttp
from django.core.servers.basehttp import WSGIServer
from maasserver.start_up import start_up


class Command(BaseRunserverCommand):
    """Customized "runserver" command that wraps the WSGI handler."""
    option_list = BaseRunserverCommand.option_list + (
        make_option(
            '--threading', action='store_true',
            dest='use_threading', default=False,
            help='Use threading for web server.'),
    )

    def run(self, *args, **options):
        threading = options.get('use_threading', False)
        if threading:
            # This is a simple backport from Django's future
            # version to support threading.
            class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
                pass
            # Monkey patch basehttp.WSGIServer.
            setattr(basehttp, 'WSGIServer', ThreadedWSGIServer)

        start_up()
        return super(Command, self).run(*args, **options)
