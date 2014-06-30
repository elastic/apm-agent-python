# -*- coding: utf-8 -*-

from opbeat.utils.compat import TestCase
from opbeat.base import Client

# Some internal stuff to extend the transport layer
from opbeat.transport import Transport

import datetime
import calendar
import pytz


class DummyScheme(Transport):

    scheme = ['mock']

    def __init__(self, parsed_url):
        self.check_scheme(parsed_url)
        self._parsed_url = parsed_url

    def send(self, data, headers):
        """
        Sends a request to a remote webserver
        """
        self._data = data
        self._headers = headers


class TransportTest(TestCase):
    def test_build_then_send(self):
        organization_id = "organization_id"
        app_id = "app_id"
        secret_token = "secret_token"

        try:
            Client.register_scheme('mock', DummyScheme)
        except:
            pass
        c = Client(organization_id=organization_id, secret_token=secret_token,
                app_id=app_id, hostname="test_server")

        mydate = datetime.datetime(2012, 5, 4, tzinfo=pytz.utc)
        d = calendar.timegm(mydate.timetuple())
        msg = c.build_msg_for_logging("Message", message='foo', date=d)
        expected = {
            'organization_id': organization_id,
            'app_id': app_id,
            'secret_token': secret_token,
            'message': 'foo',
            'param_message': {'message': 'foo', 'params': ()},
            'machine': {'hostname': u'test_server'},
            'level': "error",
            'extra': {},
            'timestamp': 1336089600
        }

        # The client_supplied_id is always overridden
        del msg['client_supplied_id']

        self.assertEquals(msg, expected)
