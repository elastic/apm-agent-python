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

from optparse import OptionParser

from opbeat_python import Client


def send_test_message(client):
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

def main():
    root = logging.getLogger('opbeat.errors')
    root.setLevel(logging.DEBUG)
    root.addHandler(logging.StreamHandler())
    
    parser = OptionParser(description=' Interface with Opbeat',
                                   prog='opbeat_python',
                                   version=opbeat_python.VERSION
                                   )

    parser.add_option("-p", "--project-id", dest="project_id",action="store",
                      help="specify project id")
    parser.add_option("-k", "--api-key",action="store",
                    dest="api_key", help="specify api key")

    parser.add_option("-k", "--api-key",action="store",
                    dest="api_key", help="specify api key")


    (options, args) = parser.parse_args()

    project_id = options.project_id or os.environ.get('OPBEAT_PROJECT_ID')
    api_key = options.api_key or os.environ.get('OPBEAT_API_KEY')

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

    pos_args = {
        'test-msg':send_test_message,
        'send-deployment':send_deployment
    }

    if len(args) < 1 or pos_args[]
