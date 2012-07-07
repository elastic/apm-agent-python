# -*- coding: utf-8 -*-

from unittest2 import TestCase
import mock

from opbeat_python.scripts.runner import build_client
from opbeat_python.conf import defaults


class ScriptRunnerTest(TestCase):
	def test_build_client(self):
		project_id = "1"
		api_key = "asda"
		
		client = build_client(project_id, api_key)

		self.assertEqual(client.servers, defaults.SERVERS)
		self.assertEqual(client.project_id, project_id)
		self.assertEqual(client.api_key, api_key)

