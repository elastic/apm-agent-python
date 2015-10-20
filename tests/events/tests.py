# -*- coding: utf-8 -*-
from __future__ import absolute_import

from mock import Mock

from opbeat.events import Message
from tests.utils.compat import TestCase


class MessageTest(TestCase):
    def test_to_string(self):
        unformatted_message = 'My message from %s about %s'
        client = Mock()
        message = Message(client)
        message.logger = Mock()
        data = {
            'param_message': {
                'message': unformatted_message,
            }
        }

        self.assertEqual(message.to_string(data), unformatted_message)

        data['param_message']['params'] = (1, 2)
        self.assertEqual(message.to_string(data),
                         unformatted_message % (1, 2))
