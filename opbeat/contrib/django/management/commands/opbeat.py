from __future__ import absolute_import

from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import color_style

from opbeat.contrib.django.models import get_client_config, get_client_class

from django.utils import termcolors

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

    def handle_command_not_found(self, command, **options):
        # TODO make this nicer
        raise CommandError('Command %s not found' % command)