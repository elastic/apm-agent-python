"""
opbeat_python.base
~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import base64
import datetime
import hashlib
import logging
import os
import time
import urllib2
import uuid
import warnings
import time
from urlparse import urlparse

import opbeat_python
from opbeat_python.conf import defaults
from opbeat_python.utils import json, varmap

from opbeat_python.utils.encoding import transform, shorten, to_string
from opbeat_python.utils.stacks import get_stack_info, iter_stack_frames, \
  get_culprit
from opbeat_python.transport import TransportRegistry

__all__ = ('Client',)


class ModuleProxyCache(dict):
	def __missing__(self, key):
		module, class_name = key.rsplit('.', 1)

		handler = getattr(__import__(module, {},
				{}, [class_name], -1), class_name)

		self[key] = handler

		return handler


class ClientState(object):
	ONLINE = 1
	ERROR = 0

	def __init__(self):
		self.status = self.ONLINE
		self.last_check = None
		self.retry_number = 0

	def should_try(self):
		if self.status == self.ONLINE:
			return True

		interval = min(self.retry_number, 6) ** 2

		if time.time() - self.last_check > interval:
			return True

		return False

	def set_fail(self):
		self.status = self.ERROR
		self.retry_number += 1
		self.last_check = time.time()

	def set_success(self):
		self.status = self.ONLINE
		self.last_check = None
		self.retry_number = 0

	def did_fail(self):
		return self.status == self.ERROR


class Client(object):
	"""
	The base opbeat_python client, which handles communication over the
	HTTP API to Opbeat servers.

	Will read default configuration from the environment variable
	``OPBEAT_PROJECT_ID`` and ``OPBEAT_API_KEY`` if available.

	>>> from opbeat import Client

	>>> # Read configuration from ``os.environ['OPBEAT_PROJECT_ID']``
	>>> # and ``os.environ['OPBEAT_API_KEY']``
	>>> client = Client()

	>>> # Specify a DSN explicitly
	>>> client =
	>>> Client(project_id='project_id', api_key='api_key')

	>>> # Configure the client manually
	>>> client = Client(
	>>>     include_paths=['my.package'],
	>>>     project='project_id',
	>>>     api_key='api_key'
	>>> )

	>>> # Record an exception
	>>> try:
	>>>     1/0
	>>> except ZeroDivisionError:
	>>>     ident = client.get_ident(client.captureException())
	>>>     print "Exception caught; reference is %%s" %% ident
	"""
	logger = logging.getLogger('opbeat')
	protocol_version = '1.0'

	_registry = TransportRegistry()

	def __init__(self, include_paths=None, exclude_paths=None,
			timeout=None, name=None, auto_log_stacks=None, key=None,
			string_max_length=None, list_max_length=None,
			project_id=None, api_key=None, processors=None,
			servers = None, api_path=None,
			**kwargs):
		# configure loggers first
		cls = self.__class__
		self.state = ClientState()
		self.logger = logging.getLogger('%s.%s' % (cls.__module__,
			cls.__name__))
		self.error_logger = logging.getLogger('opbeat.errors')

		# if isinstance(servers, basestring):
		# 	# must be a DSN:
		# 	if dsn:
		# 		# TODO: this should indicate what the caller can do to correct
		# 		# the constructor
		# 		msg = "You seem to be incorrectly instantiating the " + \
		# 			  "opbeat_python Client class"
		# 		raise ValueError(msg)
		# 	dsn = servers
		# 	servers = None

		if project_id is None and os.environ.get('OPBEAT_PROJECT_ID'):
			msg = "Configuring opbeat_python from environment variable 'OPBEAT_PROJECT_ID'"
			self.logger.info(msg)
			project_id = os.environ['OPBEAT_PROJECT_ID']

		if api_key is None and os.environ.get('OPBEAT_API_KEY'):
			msg = "Configuring opbeat_python from environment variable 'OPBEAT_API_KEY'"
			self.logger.info(msg)
			api_key = os.environ['OPBEAT_API_KEY']

		# if dsn:
		# 	# TODO: should we validate other options werent sent?
		# 	urlparts = urlparse(dsn)
		# 	msg = "Configuring opbeat_python for host: %s://%s:%s" % (urlparts.scheme,
		# 			urlparts.netloc, urlparts.path)
		# 	self.logger.info(msg)
		# 	options = opbeat_python.load(dsn, transport_registry=self._registry)
		# 	servers = options['SENTRY_SERVERS']
		# 	project = options['SENTRY_PROJECT']
		# 	public_key = options['SENTRY_PUBLIC_KEY']
		# 	secret_key = options['SENTRY_SECRET_KEY']

		self.servers = servers or defaults.SERVERS

		# servers may be set to a NoneType (for Django)
		if self.servers and not (project_id and api_key):
			msg = 'Missing configuration for client. Please see documentation.'
			raise TypeError(msg)

		self.include_paths = set(include_paths or defaults.INCLUDE_PATHS)
		self.exclude_paths = set(exclude_paths or defaults.EXCLUDE_PATHS)
		self.timeout = int(timeout or defaults.TIMEOUT)
		self.name = unicode(name or defaults.NAME)
		self.auto_log_stacks = bool(auto_log_stacks or
				defaults.AUTO_LOG_STACKS)
		
		self.string_max_length = int(string_max_length or
				defaults.MAX_LENGTH_STRING)
		self.list_max_length = int(list_max_length or defaults.MAX_LENGTH_LIST)

		self.api_key = api_key
		self.project_id = project_id

		self.processors = processors or defaults.PROCESSORS
		self.module_cache = ModuleProxyCache()

	@classmethod
	def register_scheme(cls, scheme, transport_class):
		cls._registry.register_scheme(scheme, transport_class)

	def get_processors(self):
		for processor in self.processors:
			yield self.module_cache[processor](self)

	def get_ident(self, result):
		"""
		Returns a searchable string representing a message.

		>>> result = client.process(**kwargs)
		>>> ident = client.get_ident(result)
		"""
		return '$'.join(result)

	def get_handler(self, name):
		return self.module_cache[name](self)

	def build_msg_for_logging(self, event_type, data=None, date=None,
			extra=None, stack=None,
			**kwargs):
		"""
		Captures, processes and serializes an event into a dict object
		"""

		# create ID client-side so that it can be passed to application
		event_id = uuid.uuid4().hex

		if data is None:
			data = {}
		if extra is None:
			extra = {}
		if not date:
			date = datetime.datetime.utcnow()
		if stack is None:
			stack = self.auto_log_stacks

		self.build_msg(data=data)

		# if '.' not in event_type:
			# Assume it's a builtin
		event_type = 'opbeat_python.events.%s' % event_type

		handler = self.get_handler(event_type)

		result = handler.capture(**kwargs)

		# data (explicit) culprit takes over auto event detection
		culprit = result.pop('culprit', None)
		if data.get('culprit'):
			culprit = data['culprit']

		for k, v in result.iteritems():
			if k not in data:
				data[k] = v

		if stack and 'stacktrace' not in data:
			if stack is True:
				frames = iter_stack_frames()
			else:
				frames = stack

			data.update({
				'stacktrace': {
					'frames': varmap(lambda k, v: shorten(v,
						string_length=self.string_max_length,
						list_length=self.list_max_length),
					get_stack_info(frames))
				},
			})

		if 'stacktrace' in data and not culprit:
			culprit = get_culprit(
				data['stacktrace']['frames'],
				self.include_paths, self.exclude_paths
			)

		if not data.get('level'):
			data['level'] = 'error'

		if isinstance( data['level'], ( int, long ) ):
			try:
				data['level'] = logging.getLevelName(data['level']).lower()
			except Exception, ex:
				print ex
		
		data.setdefault('extra', {})

		# Shorten lists/strings
		for k, v in extra.iteritems():
			data['extra'][k] = shorten(v, string_length=self.string_max_length,
					list_length=self.list_max_length)

		if culprit:
			data['culprit'] = culprit

		# Run the data through processors
		for processor in self.get_processors():
			data.update(processor.process(data))

		# Make sure all data is coerced
		data = transform(data)

		if 'message' not in data:
			data['message'] = handler.to_string(data)

		data.update({
			'timestamp':  date,
			# 'time_spent': time_spent,
			'client_supplied_id': event_id,
		})


		return data



	def build_msg(self, data=None,
			**kwargs):
		data.setdefault('server_name', self.name)
		data.setdefault('project_id', self.project_id)
		data.setdefault('project_id', self.project_id)
		data.setdefault('api_key', self.api_key)
		return data


	def capture(self, event_type, data=None, date=None, api_path=None,
				extra=None, stack=None, **kwargs):
		"""
		Captures and processes an event and pipes it off to SentryClient.send.

		To use structured data (interfaces) with capture:

		>>> capture('Message', message='foo', data={
		>>>     'http': {
		>>>         'url': '...',
		>>>         'data': {},
		>>>         'query_string': '...',
		>>>         'method': 'POST',
		>>>     },
		>>>     'logger': 'logger.name',
		>>>     'site': 'site.name',
		>>> }, extra={
		>>>     'key': 'value',
		>>> })

		The finalized ``data`` structure contains the following (some optional)
		builtin values:

		>>> {
		>>>     # the culprit and version information
		>>>     'culprit': 'full.module.name', # or /arbitrary/path
		>>>
		>>>     # arbitrary data provided by user
		>>>     'extra': {
		>>>         'key': 'value',
		>>>     }
		>>> }

		:param event_type: the module path to the Event class. Builtins can use
						   shorthand class notation and exclude the full module
						   path.
		:param data: the data base
		:param date: the datetime of this event
		:param client_supplied_id: a 32-length unique string identifying this event
		:param extra: a dictionary of additional standard metadata
		:param culprit: a string representing the cause of this event
						(generally a path to a function)
		:return: a 32-length string identifying this event
		"""

		data = self.build_msg_for_logging(event_type, data, date,
				extra, stack, **kwargs)

		if not api_path:
			api_path = defaults.ERROR_API_PATH 
		
		data['servers'] = [ server+api_path for server in self.servers]

		self.send(**data)

		return data['client_supplied_id']

	def _send_remote(self, url, data, headers={}):
		parsed = urlparse(url)
		transport = self._registry.get_transport(parsed)
		return transport.send(data, headers)

	def _get_log_message(self, data):
		# decode message so we can show the actual event
		try:
			data = self.decode(data)
		except:
			message = '<failed decoding data>'
		else:
			message = data.pop('message', '<no message value>')
		return message

	def send_remote(self, url, data, headers={}):
		if not self.state.should_try():
			message = self._get_log_message(data)
			self.error_logger.error(message)
			return

		try:
			self._send_remote(url=url, data=data, headers=headers)
		except Exception, e:
			if isinstance(e, urllib2.HTTPError):
				body = e.read()
				self.error_logger.error('Unable to reach Sentry log server: %s (url: %%s, body: %%s)' % (e,), url, body,
					exc_info=True, extra={'data': {'body': body, 'remote_url': url}})
			else:
				tmpl = 'Unable to reach Sentry log server: %s (url: %%s)'
				self.error_logger.error(tmpl % (e,), url, exc_info=True,
						extra={'data': {'remote_url': url}})

			message = self._get_log_message(data)
			self.error_logger.error('Failed to submit message: %r', message)
			self.state.set_fail()
		else:
			self.state.set_success()

	def send(self, project_id=None, api_key=None, auth_header=None, servers = None, **data):
		"""
		Serializes the message and passes the payload onto ``send_encoded``.
		"""
		message = self.encode(data)

		try:
			return self.send_encoded(message, project_id=project_id, api_key=api_key, auth_header=auth_header, servers=servers)
		except TypeError:
			# Make the assumption that public_key wasnt supported
			warnings.warn('%s.send_encoded needs updated to support ``**kwargs``' % (type(self).__name__,),
				DeprecationWarning)
			return self.send_encoded(message)

	def send_encoded(self, message, project_id, api_key, auth_header=None, servers = None, **kwargs):
		"""
		Given an already serialized message, signs the message and passes the
		payload off to ``send_remote`` for each server specified in the servers
		configuration.
		"""

		servers = servers or self.servers
		if not servers:
			warnings.warn('opbeat_python client has no remote servers configured')
			return

		if not auth_header:
			timestamp = time.time()
			if not project_id:
				project_id = self.project_id
				api_key = self.api_key
				
			auth_header = "apikey %s:%s" % (project_id, api_key)

		for url in servers:
			headers = {
				'Authorization': auth_header,
				'Content-Type': 'application/octet-stream',
				'User-Agent': 'opbeat_python/%s' % opbeat_python.VERSION
			}

			self.send_remote(url=url, data=message, headers=headers)

	def encode(self, data):
		"""
		Serializes ``data`` into a raw string.
		"""
		return json.dumps(data).encode('zlib')

	def decode(self, data):
		"""
		Unserializes a string, ``data``.
		"""
		return json.loads(data.decode('zlib'))

	def captureMessage(self, message, **kwargs):
		"""
		Creates an event from ``message``.

		>>> client.captureMessage('My event just happened!')
		"""
		return self.capture('Message', message=message, **kwargs)

	def captureException(self, exc_info=None, **kwargs):
		"""
		Creates an event from an exception.

		>>> try:
		>>>     exc_info = sys.exc_info()
		>>>     client.captureException(exc_info)
		>>> finally:
		>>>     del exc_info

		If exc_info is not provided, or is set to True, then this method will
		perform the ``exc_info = sys.exc_info()`` and the requisite clean-up
		for you.
		"""
		return self.capture('Exception', exc_info=exc_info, **kwargs)

	def captureQuery(self, query, params=(), engine=None, **kwargs):
		"""
		Creates an event for a SQL query.

		>>> client.captureQuery('SELECT * FROM foo')
		"""
		return self.capture('Query', query=query, params=params, engine=engine,
				**kwargs)


class DummyClient(Client):
	"Sends messages into an empty void"
	def send(self, **kwargs):
		return None
