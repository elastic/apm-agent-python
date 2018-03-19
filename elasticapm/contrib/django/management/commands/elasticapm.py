from __future__ import absolute_import

import sys

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.color import color_style
from django.utils import termcolors

from elasticapm.contrib.django.client import DjangoClient

try:
    from django.core.management.base import OutputWrapper
except ImportError:
    OutputWrapper = None


blue = termcolors.make_style(opts=('bold',), fg='blue')
cyan = termcolors.make_style(opts=('bold',), fg='cyan')
green = termcolors.make_style(fg='green')
magenta = termcolors.make_style(opts=('bold',), fg='magenta')
red = termcolors.make_style(opts=('bold',), fg='red')
white = termcolors.make_style(opts=('bold',), fg='white')
yellow = termcolors.make_style(opts=('bold',), fg='yellow')


class TestException(Exception):
    pass


class ColoredLogger(object):
    def __init__(self, stream):
        self.stream = stream
        self.errors = []
        self.color = color_style()

    def log(self, level, *args, **kwargs):
        style = kwargs.pop('style', self.color.NOTICE)
        msg = ' '.join((level.upper(), args[0] % args[1:], '\n'))
        if OutputWrapper is None:
            self.stream.write(msg)
        else:
            self.stream.write(msg, style_func=style)

    def error(self, *args, **kwargs):
        kwargs['style'] = red
        self.log('error', *args, **kwargs)
        self.errors.append((args,))

    def warning(self, *args, **kwargs):
        kwargs['style'] = yellow
        self.log('warning', *args, **kwargs)

    def info(self, *args, **kwargs):
        kwargs['style'] = green
        self.log('info', *args, **kwargs)


CONFIG_EXAMPLE = """

You can set it in your settings file:

    ELASTIC_APM = {
        'SERVICE_NAME': '<YOUR-SERVICE-NAME>',
        'SECRET_TOKEN': '<YOUR-SECRET-TOKEN>',
    }

or with environment variables:

    $ export ELASTIC_APM_SERVICE_NAME="<YOUR-SERVICE-NAME>"
    $ export ELASTIC_APM_SECRET_TOKEN="<YOUR-SECRET-TOKEN>"
    $ python manage.py elasticapm check

"""


class Command(BaseCommand):
    arguments = (
        (('-s', '--service-name'),
         {'default': None, 'dest': 'service_name', 'help': 'Specifies the service name.'}),

        (('-t', '--token'),
         {'default': None, 'dest': 'secret_token', 'help': 'Specifies the secret token.'})
    )

    args = 'test check'

    def add_arguments(self, parser):
        parser.add_argument('subcommand')
        for args, kwargs in self.arguments:
            parser.add_argument(*args, **kwargs)

    def handle(self, *args, **options):
        if 'subcommand' in options:
            subcommand = options['subcommand']
        else:
            return self.handle_command_not_found('No command specified.')
        if subcommand not in self.dispatch:
            self.handle_command_not_found('No such command "%s".' % subcommand)
        else:
            self.dispatch.get(
                subcommand,
                self.handle_command_not_found
            )(self, subcommand, **options)

    def handle_test(self, command, **options):
        """Send a test error to APM Server"""
        config = {}
        # can't be async for testing
        config['async_mode'] = False
        for key in ('service_name', 'secret_token'):
            if options.get(key):
                config[key] = options[key]
        client = DjangoClient(**config)
        client.error_logger = ColoredLogger(self.stderr)
        client.logger = ColoredLogger(self.stderr)
        client.state.logger = client.logger
        client.state.error_logger = client.error_logger
        self.write(
            "Trying to send a test error to APM Server using these settings:\n\n"
            "SERVICE_NAME:\t%s\n"
            "SECRET_TOKEN:\t%s\n"
            "SERVER:\t\t%s\n\n" % (
                client.config.service_name,
                client.config.secret_token,
                client.config.server_url,
            )
        )

        try:
            raise TestException('Hi there!')
        except TestException:
            client.capture_exception()
            if not client.error_logger.errors:
                self.write(
                    'Success! We tracked the error successfully! You should be'
                    ' able to see it in a few seconds at the above URL'
                )
        finally:
            client.close()

    def handle_check(self, command, **options):
        """Check your settings for common misconfigurations"""
        passed = True
        client = DjangoClient()
        # check if org/app and token are set:
        is_set = lambda x: x and x != 'None'
        values = [client.config.service_name, client.config.secret_token]
        if all(map(is_set, values)):
            self.write(
                'Service name and secret token are set, good job!',
                green
            )
        else:
            passed = False
            self.write(
                'Configuration errors detected!', red, ending='\n\n'
            )
            if not is_set(client.config.service_name):
                self.write("  * SERVICE_NAME not set! ", red, ending='\n')
            if not is_set(client.config.secret_token):
                self.write("  * SECRET_TOKEN not set!", red, ending='\n')
            self.write(CONFIG_EXAMPLE)
        self.write('')

        # check if we're disabled due to DEBUG:
        if settings.DEBUG:
            if getattr(settings, 'ELASTIC_APM', {}).get('DEBUG'):
                self.write(
                    'Note: even though you are running in DEBUG mode, we will '
                    'send data to the APM Server, because you set ELASTIC_APM["DEBUG"] to '
                    'True. You can disable ElasticAPM while in DEBUG mode like this'
                    '\n\n',
                    yellow
                )
                self.write(
                    '   ELASTIC_APM = {\n'
                    '       "DEBUG": False,\n'
                    '       # your other ELASTIC_APM settings\n'
                    '   }'

                )
            else:
                self.write(
                    'Looks like you\'re running in DEBUG mode. ElasticAPM will NOT '
                    'gather any data while DEBUG is set to True.\n\n',
                    red,
                )
                self.write(
                    'If you want to test ElasticAPM while DEBUG is set to True, you'
                    ' can force ElasticAPM to gather data by setting'
                    ' ELASTIC_APM["DEBUG"] to True, like this\n\n'
                    '   ELASTIC_APM = {\n'
                    '       "DEBUG": True,\n'
                    '       # your other ELASTIC_APM settings\n'
                    '   }'
                )
                passed = False
        else:
            self.write(
                'DEBUG mode is disabled! Looking good!',
                green
            )
        self.write('')

        # check if middleware is set, and if it is at the first position
        middleware = list(getattr(settings, 'MIDDLEWARE', getattr(settings, 'MIDDLEWARE_CLASSES', [])))
        try:
            pos = middleware.index(
                'elasticapm.contrib.django.middleware.TracingMiddleware'
            )
            if pos == 0:
                self.write(
                    'Tracing middleware is configured! Awesome!',
                    green
                )
            else:
                self.write(
                    'Tracing middleware is configured, but not at the first '
                    'position\n',
                    yellow
                )
                self.write(
                    'ElasticAPM works best if you add it at the top of your '
                    'MIDDLEWARE_CLASSES'
                )
        except ValueError:
            self.write(
                'Tracing middleware not configured!', red
            )
            self.write(
                '\n'
                'Add it to your MIDDLEWARE_CLASSES like this:\n\n'
                '    MIDDLEWARE_CLASSES = (\n'
                '        "elasticapm.contrib.django.middleware.TracingMiddleware",\n'
                '        # your other middleware classes\n'
                '    )\n'
            )
        self.write('')
        if passed:
            self.write('Looks like everything should be ready!', green)
        else:
            self.write(
                'Please fix the above errors.',
                red
            )
        self.write('')
        return passed

    def handle_command_not_found(self, message):
        self.write(message, red, ending='')
        self.write(
            ' Please use one of the following commands:\n\n',
            red
        )
        self.write(
            ''.join(
                ' * %s\t%s\n' % (k.ljust(8), v.__doc__)
                for k, v in self.dispatch.items()
            )
        )
        self.write('\n')
        argv = self._get_argv()
        self.write(
            'Usage:\n\t%s elasticapm <command>' % (
                ' '.join(argv[:argv.index('elasticapm')])
            )
        )

    def write(self, msg, style_func=None, ending=None, stream=None):
        """
        wrapper around self.stdout/stderr to ensure Django 1.4 compatibility
        """
        if stream is None:
            stream = self.stdout
        if OutputWrapper is None:
            ending = '\n' if ending is None else ending
            msg += ending
            stream.write(msg)
        else:
            stream.write(msg, style_func=style_func, ending=ending)

    def _get_argv(self):
        """allow cleaner mocking of sys.argv"""
        return sys.argv

    dispatch = {
        'test': handle_test,
        'check': handle_check,
    }
