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
        os.environ.pop('CEG_ALLOW_BROKER_ORDERS',None)

    def test_broker_orders_fail_closed_without_config(self):
        self.assertFalse(app.broker_orders_enabled())
        with self.assertRaisesRegex(RuntimeError,'disabled'):
            app.place_broker_order({'client_order_id':'a53-test','symbol':'SPY','qty':'1'})

    def test_broker_orders_require_config_and_runtime_interlocks(self):
        app.CFG.write_text(json.dumps({'broker_orders_enabled':'true'}))
        self.assertFalse(app.broker_orders_enabled())
        app.CFG.write_text(json.dumps({'broker_orders_enabled':True}))
        self.assertFalse(app.broker_orders_enabled())
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        self.assertTrue(app.broker_orders_enabled())

    def test_broker_endpoint_is_permanently_paper_only(self):
        self.assertEqual(app.paper_api_url('/account'),'https://paper-api.alpaca.markets/v2/account')
        with mock.patch.object(app,'PAPER','https://api.alpaca.markets/v2'):
            with self.assertRaisesRegex(RuntimeError,'non-paper'):
                app.paper_api_url('/orders')

    def test_order_retry_recovers_deterministic_client_id(self):
        app.CFG.write_text(json.dumps({'broker_orders_enabled':True}))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
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

    def test_dashboard_supports_family_vault_path_prefix(self):
        response=app.app.test_client().get('/')
        html=response.get_data(as_text=True)
        response.close()
        self.assertIn("const ASH_BASE=location.pathname==='/ash'",html)
        self.assertIn('fetch(ashUrl(p)',html)
        self.assertIn("serviceWorker.register(ashUrl('/sw.js')",html)
        self.assertIn('href="manifest.webmanifest"',html)

    def _paper_cfg(self):
        app.CFG.write_text(json.dumps({
            'alpaca_key':'k','alpaca_secret':'s','fred_key':'f','keys_ok':True,
            'broker_orders_enabled':False,
        }))

    def _wipe_trades(self):
        con=app.db(); con.execute('DELETE FROM trades'); con.commit(); con.close()

    def _run_startup(self, orders, positions):
        def fake_getj(url, headers=None, params=None, timeout=30):
            if str(url).rstrip('/').endswith('/positions'):
                return positions
            if '/orders' in str(url):
                return orders
            return {}
        with mock.patch.object(app,'getj',side_effect=fake_getj), \
             mock.patch.object(app,'ah',return_value={}), \
             mock.patch.object(app,'reconcile'):
            return app.startup_reconcile()

    def test_startup_does_not_rebuild_activity_from_flat_buys(self):
        self._paper_cfg(); self._wipe_trades()
        buy={'id':'ord1','client_order_id':'a53-20260818-mvr-meta','side':'buy','status':'filled',
             'symbol':'META260819C00547500','qty':'1','filled_avg_price':'5.7',
             'filled_at':'2026-08-18T17:26:31Z','submitted_at':'2026-08-18T17:26:30Z'}
        self._run_startup([buy], [])
        con=app.db(); n=con.execute('SELECT COUNT(*) n FROM trades').fetchone()['n']; con.close()
        self.assertEqual(n,0)

    def test_startup_recovers_filled_buy_only_when_broker_still_holds(self):
        self._paper_cfg(); self._wipe_trades()
        buy={'id':'ord1','client_order_id':'a53-20260818-mvr-meta','side':'buy','status':'filled',
             'symbol':'META260819C00547500','qty':'1','filled_avg_price':'5.7',
             'filled_at':'2026-08-18T17:26:31Z','submitted_at':'2026-08-18T17:26:30Z'}
        self._run_startup([buy], [{'symbol':'META260819C00547500','qty':'1'}])
        con=app.db(); row=con.execute('SELECT status,option_symbol FROM trades').fetchone(); con.close()
        self.assertEqual(row['status'],'OPEN')
        self.assertEqual(row['option_symbol'],'META260819C00547500')

    def test_startup_closes_local_open_from_matching_exit_id(self):
        self._paper_cfg(); self._wipe_trades()
        con=app.db()
        con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,
                       entry_fill,exit_due_date,status,horizon,exit_client_id)
                       VALUES(1,'MVR','META','CALL','META260819C00547500',1,?,?,?,5.7,?,'OPEN','EOD','x53-1')""",
                    ('2026-08-18T13:26:30-04:00','2026-08-18','2026-08-19','2026-08-18'))
        con.commit(); con.close()
        sell={'id':'ex1','client_order_id':'x53-1','side':'sell','status':'filled',
              'symbol':'META260819C00547500','qty':'1','filled_avg_price':'3.6',
              'filled_at':'2026-08-18T19:58:00Z'}
        self._run_startup([sell], [])
        con=app.db(); row=con.execute('SELECT status,pnl,exit_fill FROM trades WHERE id=1').fetchone(); con.close()
        self.assertEqual(row['status'],'CLOSED')
        self.assertEqual(row['exit_fill'],3.6)
        self.assertAlmostEqual(row['pnl'],-210.0)

    def test_startup_fails_closed_when_live_open_is_unexplained(self):
        self._paper_cfg(); self._wipe_trades()
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,
                       entry_fill,exit_due_date,status,horizon)
                       VALUES('OPN','SPY','CALL','SPY209901C00500000',1,?,?,?,1.0,?,'OPEN','EOD')""",
                    (app.now_ny().isoformat(),app.now_ny().date().isoformat(),'2099-01-01','2099-01-01'))
        con.commit(); con.close()
        with self.assertRaisesRegex(RuntimeError,'missing broker positions'):
            self._run_startup([], [])

    def test_desk_window_keeps_open_and_recent_closed(self):
        self._wipe_trades()
        today=app.now_ny().date()
        old=(today-__import__('datetime').timedelta(days=40)).isoformat()
        recent=(today-__import__('datetime').timedelta(days=2)).isoformat()
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,status,pnl,exit_filled_at)
                       VALUES('MVR','QQQ','CALL','QQQOLD',1,?,?,'2026-06-01','CLOSED',-10,?)""",
                    (old+'T10:00:00-04:00',old,old+'T16:00:00-04:00'))
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,status,pnl,exit_filled_at)
                       VALUES('MVR','SPY','PUT','SPYNEW',1,?,?,'2026-08-19','CLOSED',12,?)""",
                    (recent+'T10:00:00-04:00',recent,recent+'T16:00:00-04:00'))
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,status,horizon)
                       VALUES('OPN','NVDA','CALL','NVDAOPEN',1,?,?,'2099-01-01','OPEN','EOD')""",
                    (old+'T10:00:00-04:00',old))
        con.commit(); con.close()
        with mock.patch.object(app,'broker_positions',return_value=[]):
            rows,cutoff=app.desk_trades(30)
        ids={r['ticker'] for r in rows}
        self.assertIn('SPY',ids)
        self.assertIn('NVDA',ids)
        self.assertNotIn('QQQ',ids)
        self.assertTrue(all(r.get('dates') and r['dates'].get('trade_date') for r in rows))

    def test_account_snapshot_is_reused_when_broker_is_down(self):
        app.snapshot_account({'equity':100000,'cash':90000,'portfolio_value':100000,'last_equity':99500,
                              'buying_power':80000,'options_buying_power':80000,'daytrade_count':0})
        with mock.patch.object(app,'broker_account',side_effect=RuntimeError('down')):
            got=app.live_or_stored_account()
        self.assertEqual(got.get('source'),'snapshot')
        self.assertEqual(got.get('equity'),100000)


if __name__=='__main__':
    unittest.main()
