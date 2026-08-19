import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


_tmp=tempfile.TemporaryDirectory()
os.environ['CEG_ENV']='test'
os.environ['CEG_DATA_DIR']=str(Path(_tmp.name)/'data')
os.environ['CEG_CONFIG_FILE']=str(Path(_tmp.name)/'config.test.json')

import app


class SafetyTests(unittest.TestCase):
    def setUp(self):
        app.CFG.unlink(missing_ok=True)

    def test_broker_orders_fail_closed_without_config(self):
        self.assertFalse(app.broker_orders_enabled())
        with self.assertRaisesRegex(RuntimeError,'disabled'):
            app.place_broker_order({'client_order_id':'a53-test','symbol':'SPY','qty':'1'})

    def test_broker_orders_require_literal_true(self):
        app.CFG.write_text(json.dumps({'broker_orders_enabled':'true'}))
        self.assertFalse(app.broker_orders_enabled())
        app.CFG.write_text(json.dumps({'broker_orders_enabled':True}))
        self.assertTrue(app.broker_orders_enabled())

    def test_order_retry_recovers_deterministic_client_id(self):
        app.CFG.write_text(json.dumps({'broker_orders_enabled':True}))
        expected={'id':'existing','client_order_id':'a53-20260818-ceg-spy'}
        with mock.patch.object(app,'broker_order_by_client_id',side_effect=[None,expected]), \
             mock.patch.object(app,'postj',side_effect=RuntimeError('lost response')) as post:
            got=app.place_broker_order({'client_order_id':expected['client_order_id'],'symbol':'SPY','qty':'1'})
        self.assertEqual(got,expected)
        post.assert_called_once()

    def test_health_fails_without_runner_heartbeat(self):
        con=app.db(); con.execute("DELETE FROM meta WHERE k='heartbeat'"); con.commit(); con.close()
        self.assertFalse(app.runner_health()['ok'])
        response=app.app.test_client().get('/api/health')
        self.assertEqual(response.status_code,503)

    def test_import_does_not_start_runner(self):
        con=app.db(); row=con.execute("SELECT v FROM meta WHERE k='runner_pid'").fetchone(); con.close()
        self.assertIsNone(row)

    def test_broken_stdout_does_not_escape_event_logging(self):
        with mock.patch('builtins.print',side_effect=BrokenPipeError):
            app.event('pipe disappeared')


if __name__=='__main__':
    unittest.main()
