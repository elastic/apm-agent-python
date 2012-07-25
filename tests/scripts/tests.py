# -*- coding: utf-8 -*-

from unittest2 import TestCase
import mock

from opbeat_python.scripts.runner import build_client
from opbeat_python.conf import defaults


class ScriptRunnerTest(TestCase):
	def test_build_client(self):
		project_id = "1"
		access_token = "asda"
		
		client = build_client(project_id, access_token)

		self.assertEqual(client.servers, defaults.SERVERS)
		self.assertEqual(client.project_id, project_id)
		self.assertEqual(client.access_token, access_token)

