from __future__ import absolute_import

from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import color_style
from django.utils import termcolors

from opbeat.contrib.django.models import get_client_config, get_client_class


blue = termcolors.make_style(opts=('bold',), fg='blue')
cyan = termcolors.make_style(opts=('bold',), fg='cyan')
green = termcolors.make_style(fg='green')
magenta = termcolors.make_style(opts=('bold',), fg='magenta')
red = termcolors.make_style(opts=('bold',), fg='red')
white = termcolors.make_style(opts=('bold',), fg='white')
yellow = termcolors.make_style(opts=('bold',), fg='yellow')


class OpbeatTestException(Exception):
    pass


class Logger(object):
    def __init__(self, stream):
        self.stream = stream
        self.errors = []
        self.color = color_style()

    def log(self, level, *args, **kwargs):
        style = kwargs.pop('style', self.color.NOTICE)
        self.stream.write(
            ' '.join((level.upper(), args[0] % args[1:], '\n')),
            style_func=style
        )

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
    option_list = BaseCommand.option_list + (
        make_option('-o', '--organization-id', default=None,
                    dest='organization_id',
                    help='Specifies the organization ID.'),
        make_option('-a', '--app-id', default=None,
                    dest='app_id',
                    help='Specifies the app ID.'),
        make_option('-t', '--token', default=None,
                    dest='secret_token',
                    help='Specifies the secret token.'),
    )
    args = 'test check'

    def handle(self, *args, **options):
        dispatch = {
            'test': self.handle_test,
            'check': self.handle_check,
        }
        dispatch.get(
            args[0],
            self.handle_command_not_found
        )(args[0], **options)

    def handle_test(self, command, **options):
        config = get_client_config()
        # can't be async for testing
        config['async'] = False
        for key in ('organization_id', 'app_id', 'secret_token'):
            if options.get(key):
                config[key] = options[key]
        client_class = get_client_class()
        client = client_class(**config)
        client.error_logger = Logger(self.stderr)
        client.logger = Logger(self.stderr)
        client.state.logger = client.logger
        client.state.error_logger = client.error_logger
        self.stdout.write(
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
            result = client.captureException()
            if not client.error_logger.errors:
                self.stdout.write(
                    'Success! We tracked the error successfully! You should be able'
                    ' to see it in a few seconds at the above URL'
                )

    def handle_check(self, command, **options):
        """TODO: ideally, this would call a check endpoint at the intake that
                does some more involved checking"""
        passed = True
        config = get_client_config()
        client_class = get_client_class()
        client = client_class(**config)
        # check if org/app and token are set:
        if all([client.organization_id, client.app_id, client.secret_token]):
            self.stdout.write(
                'Organization, app and secret token are set, good job!',
                green
            )
        else:
            passed = False
            if not client.organization_id:
                self.stdout.write("Organization not set! ", red, ending='')
            if not client.app_id:
                self.stdout.write("Application not set! ", red, ending='')
            if not client.secret_token:
                self.stdout.write("Secret token not set!", red, ending='')
            self.stdout.write(CONFIG_EXAMPLE)
        self.stdout.write('')

        # check if we're disabled due to DEBUG:
        if settings.DEBUG:
            if getattr(settings, 'OPBEAT', {}).get('DEBUG'):
                self.stdout.write(
                    'Note: even though you are running in DEBUG mode, we will '
                    'send data to Opbeat, because you set OPBEAT["DEBUG"] to '
                    'True. You can disable Opbeat while in DEBUG mode like this'
                    '\n\n',
                    yellow
                )
                self.stdout.write(
                    '   OPBEAT = {\n'
                    '       "DEBUG": False,\n'
                    '       # your other OPBEAT settings\n'
                    '   }'

                )
            else:
                self.stdout.write(
                    'Looks like you\'re running in DEBUG mode. Opbeat will NOT '
                    'gather any data while DEBUG is set to True.\n\n',
                    red,
                )
                self.stdout.write(
                    'If you want to test Opbeat while DEBUG is set to True, you '
                    'can force Opbeat to gather data by setting OPBEAT["DEBUG"] '
                    'to True, like this\n\n'
                    '   OPBEAT = {\n'
                    '       "DEBUG": True,\n'
                    '       # your other OPBEAT settings\n'
                    '   }'
                )
                passed = False
        else:
            self.stdout.write(
                'DEBUG mode is disabled! Lookin\' good!',
                green
            )
        self.stdout.write('')

        # check if middleware is set, and if it is at the first position
        middleware = list(settings.MIDDLEWARE_CLASSES)
        try:
            pos = middleware.index(
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware'
            )
            if pos == 0:
                self.stdout.write(
                    'Opbeat APM middleware is set! Awesome!',
                    green
                )
            else:
                self.stdout.write(
                    'Opbeat APM middleware is set, but not at the first position\n',
                    yellow
                )
                self.stdout.write(
                    'Opbeat APM work best if you add it at the top of your '
                    'MIDDLEWARE_CLASSES'
                )
        except ValueError:
            self.stdout.write(
                'Opbeat APM middleware not set!', red
            )
            self.stdout.write(
                '\n'
                'Add it to your MIDDLEWARE_CLASSES like this:\n\n'
                '    MIDDLEWARE_CLASSES = (\n'
                '        "opbeat.contrib.django.middleware.OpbeatAPMMiddleware",\n'
                '        # your other middleware classes\n'
                '    )\n'
            )
        self.stdout.write('')
        if passed:
            self.stdout.write('Looks like everything should be ready!', green)
        else:
            self.stdout.write(
                'Please fix the above errors. If you have any questions, write '
                'us at support@opbeat.com!',
                red
            )
        self.stdout.write('')
        return passed

    def handle_command_not_found(self, command, **options):
        # TODO make this nicer
        raise CommandError('Command %s not found' % command)