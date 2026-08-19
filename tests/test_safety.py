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
        self.assertIn("xhair=bars[index]?.t??null",html)
        self.assertNotIn("[{date:null,cumPnl:0}]",html)
        self.assertIn("Date.now()-(chartDataAt[t]||0)>60000",html)
        self.assertIn("s.filter(x=>(x.closed||0)>0)",html)
        self.assertIn("['SPY','QQQ','IWM'].includes(t)?'INDEX':'EQUITY'",html)
        self.assertIn('amber squares = flat',html)

    def _paper_cfg(self):
        app.CFG.write_text(json.dumps({
            'alpaca_key':'k','alpaca_secret':'s','fred_key':'f','keys_ok':True,
            'broker_orders_enabled':False,
        }))

    def _wipe_trades(self):
        con=app.db(); con.execute('DELETE FROM trades'); con.commit(); con.close()

    def _run_startup(self, orders, positions):
        frozen=app.datetime(2026,8,19,16,30,tzinfo=app.NY)
        def fake_getj(url, headers=None, params=None, timeout=30):
            if str(url).rstrip('/').endswith('/positions'):
                return positions
            if '/orders' in str(url):
                return orders
            return {}
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'getj',side_effect=fake_getj), \
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

    def test_ledger_repair_pairs_legacy_duplicate_contracts_once_in_time_order(self):
        self._wipe_trades()
        con=app.db()
        for tid,fill,entered in ((1,2.0,'2026-08-18T14:11:28Z'),(2,1.6,'2026-08-18T14:18:32Z')):
            con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,
                           expiry,entry_order_id,entry_client_id,entry_fill,entry_filled_at,exit_due_date,status,pnl,exit_kind)
                           VALUES(?,'ORB','QQQ','PUT','QQQ260818P00718000',1,?,'2026-08-18','2026-08-18',
                           ?,?, ?,?,'2026-08-18','CLOSED',?,'EXPIRED')""",
                        (tid,entered,f'buy{tid}',f'a53-orb-qqq-{tid}',fill,entered,-fill*100))
        con.commit(); con.close()
        sells=[
            {'id':'sell1','client_order_id':'x53-orb-qqq-1','side':'sell','status':'filled',
             'symbol':'QQQ260818P00718000','filled_avg_price':'1.03','filled_at':'2026-08-18T14:26:40Z'},
            {'id':'sell2','client_order_id':'x53-orb-qqq-2','side':'sell','status':'filled',
             'symbol':'QQQ260818P00718000','filled_avg_price':'0.96','filled_at':'2026-08-18T14:33:52Z'},
        ]
        plan=app.broker_ledger_repair_plan(sells)
        self.assertEqual([(x['trade_id'],x['exit_order_id'],x['pnl']) for x in plan],
                         [(1,'sell1',-97.0),(2,'sell2',-64.0)])
        self.assertEqual(app.apply_broker_ledger_repair(plan),{'updated':2,'inserted':0})
        con=app.db(); rows=con.execute('SELECT id,exit_order_id,pnl,exit_kind FROM trades ORDER BY id').fetchall(); con.close()
        self.assertEqual([(r['id'],r['exit_order_id'],r['pnl'],r['exit_kind']) for r in rows],
                         [(1,'sell1',-97.0,'BROKER_REPAIR'),(2,'sell2',-64.0,'BROKER_REPAIR')])

    def test_ledger_repair_recovers_missing_closed_round_trip(self):
        self._wipe_trades()
        buy={'id':'buy1','client_order_id':'a53-20260819-orb-iwm','side':'buy','status':'filled',
             'symbol':'IWM260819P00302000','qty':'1','filled_qty':'1','filled_avg_price':'0.75',
             'submitted_at':'2026-08-19T14:12:43Z','filled_at':'2026-08-19T14:12:44Z'}
        sell={'id':'sell1','client_order_id':'x53-9','side':'sell','status':'filled',
              'symbol':'IWM260819P00302000','qty':'1','filled_qty':'1','filled_avg_price':'0.45',
              'submitted_at':'2026-08-19T14:28:02Z','filled_at':'2026-08-19T14:28:03Z'}
        plan=app.broker_ledger_repair_plan([buy,sell])
        self.assertEqual(len(plan),1)
        self.assertEqual(plan[0]['action'],'insert')
        self.assertEqual(plan[0]['pnl'],-30.0)
        self.assertEqual(app.apply_broker_ledger_repair(plan),{'updated':0,'inserted':1})
        con=app.db(); row=con.execute('SELECT strategy_id,ticker,status,pnl,exit_order_id FROM trades').fetchone(); con.close()
        self.assertEqual((row['strategy_id'],row['ticker'],row['status'],row['pnl'],row['exit_order_id']),
                         ('ORB','IWM','CLOSED',-30.0,'sell1'))

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

    def test_dashboard_omits_unknown_closed_pnl_from_every_aggregate(self):
        self._wipe_trades(); app._MEM_CACHE.clear()
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,status,pnl,trade_date,exit_filled_at)
                       VALUES('MVR','QQQ','CLOSED',NULL,'2026-08-18','2026-08-18T16:00:00Z')""")
        con.execute("""INSERT INTO trades(strategy_id,ticker,status,pnl,trade_date,exit_filled_at)
                       VALUES('MVR','QQQ','CLOSED',10,'2026-08-19','2026-08-19T16:00:00Z')""")
        con.commit(); con.close()
        with mock.patch.object(app,'compute_research_metrics',return_value={'strategies':[]}):
            payload=app.dashboard_payload()
        mvr=next(x for x in payload['strategies'] if x['id']=='MVR')
        self.assertEqual((mvr['closed'],mvr['wins'],mvr['pnl']),(1,1,10.0))
        self.assertEqual(payload['totals']['realizedPnl'],10.0)
        self.assertEqual(len(payload['curve']),1)

    def test_dashboard_books_overnight_pnl_on_new_york_exit_date(self):
        self._wipe_trades(); app._MEM_CACHE.clear()
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,status,pnl,trade_date,exit_filled_at)
                       VALUES('CEG','SPY','CLOSED',25,'2026-08-18','2026-08-19T13:35:00Z')""")
        con.commit(); con.close()
        frozen=app.datetime(2026,8,19,12,0,tzinfo=app.NY)
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'compute_research_metrics',return_value={'strategies':[]}):
            payload=app.dashboard_payload()
        self.assertEqual(payload['dailyPnl'],[{'date':'2026-08-19','pnl':25.0}])
        self.assertEqual(payload['curve'][0]['date'],'2026-08-19')
        self.assertEqual(payload['totals']['realizedToday'],25.0)

    def test_dashboard_books_unordered_expiry_on_economic_expiry_date(self):
        self._wipe_trades(); app._MEM_CACHE.clear()
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,status,pnl,trade_date,expiry,exit_filled_at,exit_kind)
                       VALUES('MVR','IWM','CLOSED',-2,'2026-08-17','2026-08-17','2026-08-18T13:35:00Z','EXPIRED')""")
        con.commit(); con.close()
        with mock.patch.object(app,'compute_research_metrics',return_value={'strategies':[]}):
            payload=app.dashboard_payload()
        self.assertEqual(payload['dailyPnl'],[{'date':'2026-08-17','pnl':-2.0}])
        self.assertEqual(payload['curve'][0]['date'],'2026-08-17')

    def test_model_drift_forward_n_excludes_open_and_unknown_pnl(self):
        self._wipe_trades()
        con=app.db()
        con.execute("INSERT INTO trades(strategy_id,ticker,status,pnl,trade_date) VALUES('MVR','QQQ','OPEN',NULL,'2026-08-19')")
        con.execute("INSERT INTO trades(strategy_id,ticker,status,pnl,trade_date) VALUES('MVR','QQQ','CLOSED',NULL,'2026-08-19')")
        con.execute("INSERT INTO trades(strategy_id,ticker,status,pnl,trade_date) VALUES('MVR','QQQ','CLOSED',12,'2026-08-19')")
        con.commit(); con.close()
        rows=app.app.test_client().get('/api/model_drift').get_json()['rows']
        mvr=next(x for x in rows if x['id']=='MVR')
        self.assertEqual((mvr['n'],mvr['live_win_rate'],mvr['live_avg_pnl']),(1,1.0,12.0))

    def test_daily_chart_cache_requires_requested_session_depth(self):
        con=app.db(); con.execute("DELETE FROM live_bars WHERE ticker='SPY' AND timeframe='1Day'")
        for i in range(25):
            con.execute("""INSERT INTO live_bars(ingested_at,trade_date,ticker,timeframe,t,o,h,l,c,v)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (app.now_ny().isoformat(),f'2026-07-{(i%25)+1:02d}','SPY','1Day',f'2026-07-{(i%25)+1:02d}',1,1,1,1,1))
        con.commit(); con.close()
        self.assertIn('SPY',app.daily_cache_missing(['SPY'],90))
        self.assertNotIn('SPY',app.daily_cache_missing(['SPY'],20))

    def test_option_contract_refuses_next_day_as_0dte(self):
        frozen=app.datetime(2026,8,19,11,0,tzinfo=app.NY)
        nxt=app.next_trading_date('2026-08-19')
        payload={'option_contracts':[{
            'symbol':'META260820C00500000','expiration_date':nxt,'strike_price':'100',
        }]}
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'getj',return_value=payload) as gj, \
             mock.patch.object(app,'ah',return_value={}):
            with self.assertRaisesRegex(RuntimeError,'same-day'):
                app.option_contract('META','CALL',100,allow_0dte=True,style={'dte':'0dte','moneyness':'atm'})
        self.assertEqual(gj.call_count,1)
        self.assertEqual(gj.call_args[0][0], app.paper_api_url('/options/contracts'))
        params=gj.call_args[0][2]
        self.assertEqual(params['expiration_date_gte'],'2026-08-19')
        self.assertEqual(params['expiration_date_lte'],'2026-08-19')

    def test_pdt_blocks_flagged_eod_under_25k_not_overnight(self):
        acct={'equity':10000,'daytrade_count':0,'pattern_day_trader':True}
        with mock.patch.object(app,'broker_account',return_value=acct):
            self.assertIn('PDT', app.pdt_block('EOD'))
            self.assertIsNone(app.pdt_block('OVERNIGHT'))

    def test_pdt_blocks_eod_when_account_unread(self):
        with mock.patch.object(app,'broker_account',side_effect=RuntimeError('down')):
            self.assertIn('unread', app.pdt_block('EOD'))
            self.assertIsNone(app.pdt_block('OVERNIGHT'))

    def test_guest_lan_cannot_post_intro_save(self):
        response=app.app.test_client().post(
            '/api/intro-save?name=intro-flakes-white.webm',
            data=b'not-a-video',
            environ_base={'REMOTE_ADDR':'10.8.0.9'})
        self.assertEqual(response.status_code,403)
        self.assertTrue((response.get_json() or {}).get('guest'))

    def test_comments_post_allowed_when_unarmed(self):
        con=app.db()
        con.execute("INSERT INTO trades(strategy_id,ticker,direction,status,trade_date) VALUES('ORB','QQQ','CALL','OPEN','2026-08-19')")
        tid=con.execute('SELECT last_insert_rowid() x').fetchone()['x']
        con.commit(); con.close()
        client=app.app.test_client()
        empty=client.post('/api/comments',json={'kind':'INTENT','target_type':'trade','target_id':tid,'body':'  '})
        self.assertEqual(empty.status_code,400)
        ok=client.post('/api/comments',json={'kind':'INTENT','target_type':'trade','target_id':tid,'body':'gap held'})
        self.assertEqual(ok.status_code,200)
        rows=client.get(f'/api/comments?trade_id={tid}').get_json()['comments']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['kind'],'INTENT')
        self.assertEqual(rows[0]['body'],'gap held')

    def test_explain_omits_vix_when_capitulation_allowed(self):
        with mock.patch.object(app,'session_clock',return_value={'hm':'12:00','phase':'MVR','label':'VWAP reversion fade','current':['MVR'],'next':None,'remaining':30}):
            blocked=app.explain_now(ws={'vix':12.0})
            allowed=app.explain_now(ws={'vix':18.0})
        self.assertTrue(any('blocked' in p.lower() for p in blocked['paragraphs']))
        self.assertFalse(any('VIX' in p for p in allowed['paragraphs']))


if __name__=='__main__':
    unittest.main()
