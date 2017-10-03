# -*- coding: utf-8 -*-
from __future__ import absolute_import

from mock import Mock

from elasticapm.events import Message


def test_event_to_string():
    unformatted_message = 'My message from %s about %s'
    formatted_message = unformatted_message % (1, 2)
    client = Mock()
    message = Message()
    message.logger = Mock()
    data = {
        'log': {
            'message': unformatted_message % (1, 2),
            'param_message': unformatted_message,
        }
    }

    assert message.to_string(client, data) == formatted_message
