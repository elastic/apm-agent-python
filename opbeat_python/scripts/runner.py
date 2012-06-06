"""
opbeat_python.scripts.runner
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2012 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging
import os
import sys
import pwd

from opbeat_python import Client


def main():
    root = logging.getLogger('sentry.errors')
    root.setLevel(logging.DEBUG)
    root.addHandler(logging.StreamHandler())
    
    if len(sys.argv) == 3:
        project_id = sys.argv[1]
        api_key = sys.argv[2]
    else:
        project_id = os.environ.get('OPBEAT_PROJECT_ID')
        api_key = os.environ.get('OPBEAT_API_KEY')

    if not (project_id and api_key):
        print "Error: No configuration detected!"
        print "You must either pass a project_id and api_key to the command, or set the OPBEAT_PROJECT_ID and OPBEAT_API_KEY environment variables."
        sys.exit(1)

    print "Using configuration:"
    print " ", project_id
    print " ", api_key
    print 

    client = Client(project_id=project_id, api_key=api_key, include_paths=['opbeat_python'])

    print "Client configuration:"
    for k in ('servers', 'project_id', 'api_key'):
        print '  %-15s: %s' % (k, getattr(client, k))
    print

    if not all([client.servers, client.project_id, client.api_key]):
        print "Error: All values must be set!"
        sys.exit(1)

    print 'Sending a test message...',
    ident = client.get_ident(client.captureMessage(
        message='This is a test message generated using ``opbeat_python test``',
        data={
            'culprit': 'opbeat_python.scripts.runner',
            'logger': 'opbeat_python.test',
            'http': {
                'method': 'GET',
                'url': 'http://example.com',
            }
        },
        level=logging.INFO,
        stack=True,
        extra={
            'user': pwd.getpwuid(os.geteuid())[0],
            'loadavg': os.getloadavg(),
        }
    ))

    if client.state.did_fail():
        print 'error!'
        return False

    print 'success!'
    print
    print 'The test message can be viewed at the following URL:'
    url = client.servers[0].split('/api/store/', 1)[0]
    print '  %s/%s/search/?q=%s' % (url, client.project, ident)
