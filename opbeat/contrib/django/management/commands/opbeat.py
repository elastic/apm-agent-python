from __future__ import absolute_import

import sys
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import color_style
from django.utils import termcolors

from opbeat.contrib.django.models import get_client_class, get_client_config

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


class OpbeatTestException(Exception):
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


LOGO = """

                              .o8                               .
                             "888                             .o8
         .ooooo.  oo.ooooo.   888oooo.   .ooooo.   .oooo.   .o888oo
        d88' `88b  888' `88b  d88' `88b d88' `88b `P  )88b    888
        888   888  888   888  888   888 888ooo888  .oP"888    888
        888   888  888   888  888   888 888    .o d8(  888    888 .
        `Y8bod8P'  888bod8P'  `Y8bod8P' `Y8bod8P' `Y888""8o   "888"
                   888
                  o888o

"""


CONFIG_EXAMPLE = """

You can set it in your settings file:

    OPBEAT = {
        'ORGANIZATION_ID': '<YOUR-ORGANIZATION-ID>',
        'APP_ID': '<YOUR-APP-ID>',
        'SECRET_TOKEN': '<YOUR-SECRET-TOKEN>',
    }

or with environment variables:

    $ export OPBEAT_ORGANIZATION_ID="<YOUR-ORGANIZATION-ID>"
    $ export OPBEAT_APP_ID="<YOUR-APP-ID>"
    $ export OPBEAT_SECRET_TOKEN="<YOUR-SECRET-TOKEN>"
    $ python manage.py opbeat check

"""


class Command(BaseCommand):
    arguments = (
        (('-o', '--organization-id'),
         {'default': None, 'dest': 'organization_id',
          'help': 'Specifies the organization ID.'}
         ),

        (('-a', '--app-id'),
         {'default': None, 'dest': 'app_id', 'help': 'Specifies the app ID.'}
        ),

        (('-t', '--token'),
         {'default': None, 'dest': 'secret_token',
          'help': 'Specifies the secret token.'}
         )
    )
    if not hasattr(BaseCommand, 'add_arguments'):
        # Django <= 1.7
        option_list = BaseCommand.option_list + tuple(
            make_option(*args, **kwargs) for args, kwargs in arguments
        )
    args = 'test check'

    # Django 1.8+
    def add_arguments(self, parser):
        for args, kwargs in self.arguments:
            parser.add_argument(*args, **kwargs)

    def handle(self, *args, **options):
        if not args:
            self.handle_command_not_found('No command specified.')
        elif args[0] not in self.dispatch:
            self.handle_command_not_found('No such command "%s".' % args[0])
        else:
            self.dispatch.get(
                args[0],
                self.handle_command_not_found
            )(self, args[0], **options)

    def handle_test(self, command, **options):
        """Send a test error to Opbeat"""
        self.write(LOGO, cyan)
        config = get_client_config()
        # can't be async for testing
        config['async_mode'] = False
        for key in ('organization_id', 'app_id', 'secret_token'):
            if options.get(key):
                config[key] = options[key]
        client_class = get_client_class()
        client = client_class(**config)
        client.error_logger = ColoredLogger(self.stderr)
        client.logger = ColoredLogger(self.stderr)
        client.state.logger = client.logger
        client.state.error_logger = client.error_logger
        self.write(
            "Trying to send a test error to Opbeat using these settings:\n\n"
            "ORGANIZATION_ID:\t%s\n"
            "APP_ID:\t\t\t%s\n"
            "SECRET_TOKEN:\t\t%s\n"
            "SERVERS:\t\t%s\n\n" % (
                client.organization_id,
                client.app_id,
                client.secret_token,
                ', '.join(client.servers)
            )
        )

        try:
            raise OpbeatTestException('Hi there!')
        except OpbeatTestException as e:
            result = client.capture_exception()
            if not client.error_logger.errors:
                self.write(
                    'Success! We tracked the error successfully! You should be'
                    ' able to see it in a few seconds at the above URL'
                )

    def handle_check(self, command, **options):
        """Check your settings for common misconfigurations"""
        self.write(LOGO, cyan)
        passed = True
        config = get_client_config()
        client_class = get_client_class()
        client = client_class(**config)
        # check if org/app and token are set:
        is_set = lambda x: x and x != 'None'
        values = [client.organization_id, client.app_id, client.secret_token]
        if all(map(is_set, values)):
            self.write(
                'Organization, app and secret token are set, good job!',
                green
            )
        else:
            passed = False
            self.write(
                'Configuration errors detected!', red, ending='\n\n'
            )
            if not is_set(client.organization_id):
                self.write(
                    "  * ORGANIZATION_ID not set! ", red, ending='\n'
                )
            if not is_set(client.app_id):
                self.write("  * APP_ID not set! ", red, ending='\n')
            if not is_set(client.secret_token):
                self.write("  * SECRET_TOKEN not set!", red, ending='\n')
            self.write(CONFIG_EXAMPLE)
        self.write('')

        # check if we're disabled due to DEBUG:
        if settings.DEBUG:
            if getattr(settings, 'OPBEAT', {}).get('DEBUG'):
                self.write(
                    'Note: even though you are running in DEBUG mode, we will '
                    'send data to Opbeat, because you set OPBEAT["DEBUG"] to '
                    'True. You can disable Opbeat while in DEBUG mode like this'
                    '\n\n',
                    yellow
                )
                self.write(
                    '   OPBEAT = {\n'
                    '       "DEBUG": False,\n'
                    '       # your other OPBEAT settings\n'
                    '   }'

                )
            else:
                self.write(
                    'Looks like you\'re running in DEBUG mode. Opbeat will NOT '
                    'gather any data while DEBUG is set to True.\n\n',
                    red,
                )
                self.write(
                    'If you want to test Opbeat while DEBUG is set to True, you'
                    ' can force Opbeat to gather data by setting'
                    ' OPBEAT["DEBUG"] to True, like this\n\n'
                    '   OPBEAT = {\n'
                    '       "DEBUG": True,\n'
                    '       # your other OPBEAT settings\n'
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
        middleware = list(settings.MIDDLEWARE_CLASSES)
        try:
            pos = middleware.index(
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware'
            )
            if pos == 0:
                self.write(
                    'Opbeat APM middleware is set! Awesome!',
                    green
                )
            else:
                self.write(
                    'Opbeat APM middleware is set, but not at the first '
                    'position\n',
                    yellow
                )
                self.write(
                    'Opbeat APM works best if you add it at the top of your '
                    'MIDDLEWARE_CLASSES'
                )
        except ValueError:
            self.write(
                'Opbeat APM middleware not set!', red
            )
            self.write(
                '\n'
                'Add it to your MIDDLEWARE_CLASSES like this:\n\n'
                '    MIDDLEWARE_CLASSES = (\n'
                '        "opbeat.contrib.django.middleware.OpbeatAPMMiddleware",\n'
                '        # your other middleware classes\n'
                '    )\n'
            )
        self.write('')
        if passed:
            self.write('Looks like everything should be ready!', green)
        else:
            self.write(
                'Please fix the above errors. If you have any questions, write '
                'us at support@opbeat.com!',
                red
            )
        self.write('')
        return passed

    def handle_command_not_found(self, message):
        self.write(LOGO, cyan)
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
            'Usage:\n\t%s opbeat <command>' % (
                ' '.join(argv[:argv.index('opbeat')])
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
