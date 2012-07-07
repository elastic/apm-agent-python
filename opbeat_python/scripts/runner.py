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

from optparse import OptionParser, IndentedHelpFormatter, textwrap

from opbeat_python.conf import defaults
from opbeat_python.base import Client
import opbeat_python

class IndentedHelpFormatterWithNL(IndentedHelpFormatter):
	def format_description(self, description):
		if not description: return ""
		desc_width = self.width - self.current_indent
		indent = " "*self.current_indent
		
		bits = description.split('\n')
		formatted_bits = [
			textwrap.fill(bit,
			desc_width,
			initial_indent=indent,
			subsequent_indent=indent)
			for bit in bits]
		result = "\n".join(formatted_bits) + "\n"
		return result



def get_options():
	from optparse import make_option
	return (
		make_option("-p", "--project-id", dest="project_id",action="store",
						  help="specify project id"),
		make_option("-k", "--api-key",action="store",
						dest="api_key", help="specify api key"),
		make_option("-s", "--server",action="store",
						dest="server", help="override server"),
	)

def send_test_message(client, *args):
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
	
def send_deployment(client, args):
	print 'Sending a deployment info...'

	if len(args) > 0:
		directory = os.path.abspath(args[0])
		print "Using directory:", directory
	else:
		directory = None

	client.send_deployment_info(directory=directory)

	if client.state.did_fail():
		print 'error!'
		return False

	print 'success!'

def build_client(project_id = None, api_key=None, server=None):
	project_id = project_id or os.environ.get('OPBEAT_PROJECT_ID')
	api_key = api_key or os.environ.get('OPBEAT_API_KEY')

	if not (project_id and api_key):
		print "Error: No configuration detected!"
		print "You must either pass a project_id and api_key to the command, or set the OPBEAT_PROJECT_ID and OPBEAT_API_KEY environment variables."
		print 
		return False

	servers = [server] or [os.environ.get('OPBEAT_SERVER')] or defaults.SERVERS

	# print "Using configuration:"
	# print " ", project_id
	# print " ", api_key
	# print 

	client = Client(project_id=project_id, api_key=api_key, include_paths=['opbeat_python'], servers = servers)

	print "Client configuration:"
	for k in ('servers', 'project_id', 'api_key'):
		print '  %-15s: %s' % (k, getattr(client, k))
	print

	if not all([client.servers, client.project_id, client.api_key]):
		print "Error: All values must be set!"
		print 
		return False

	return client

def main():
	root = logging.getLogger('opbeat.errors')
	root.setLevel(logging.DEBUG)
	root.addHandler(logging.StreamHandler())
	
	pos_args = {
		'test-msg':send_test_message,
		'send-deployment':send_deployment
	}
	desc = ' Interface with Opbeat'
	desc += """\n\nCommands supported are: \n"""
	desc += """\n - """+"""\n - """.join([k for k in pos_args]) + "\n"

	parser = OptionParser(description=desc,
								   prog='opbeat_python',
								   version=opbeat_python.VERSION,
								   option_list=get_options(),
								   usage = "usage: %prog [options] command",
							       formatter=IndentedHelpFormatterWithNL()

								   )

	# parser.add_option("-k", "--api-key",action="store",
	#                 dest="api_key", help="specify api key")


	(options, args) = parser.parse_args()

	client = build_client(options.project_id, options.api_key, options.server)

	if not client:
		parser.print_help()
		return


	if len(args) < 1 or args[0] not in pos_args:
		parser.print_help()
	else:
		pos_args[args[0]](client, args[1:])

# if __name__ == "__main__" and __package__ is None:
#     __package__ = "opbeat_python"

if __name__ == '__main__':
	main()
