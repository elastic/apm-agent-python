"""
TODO: This needs to be fleshed out as a Sentry service
"""
import zmq
import json
from opbeat.utils import six

CONTEXT = zmq.Context()
socket = CONTEXT.socket(zmq.SUB)
socket.bind("tcp://127.0.0.1:5000")
socket.setsockopt(zmq.SUBSCRIBE, '')

while True:
    data = socket.recv()
    jdata = json.loads(data)
    six.print_(jdata)
