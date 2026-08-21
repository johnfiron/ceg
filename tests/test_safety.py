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

    def test_production_web_role_cannot_arm_or_read_broker_credentials(self):
        app.CFG.write_text(json.dumps({
            'alpaca_key':'key','alpaca_secret':'secret','broker_orders_enabled':True,
        }))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        with mock.patch.object(app,'ENVIRONMENT','production'), mock.patch.object(app,'PROCESS_ROLE','web'):
            self.assertFalse(app.broker_runtime_armed())
            self.assertFalse(app.broker_orders_enabled())
            with self.assertRaisesRegex(RuntimeError,'credentials are unavailable'):
                app.ah()
            with self.assertRaisesRegex(RuntimeError,'runner-only'):
                app.place_broker_order({'client_order_id':'web-must-fail'})

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

    def test_production_web_is_read_only_even_behind_loopback_proxy(self):
        client=app.app.test_client()
        attempts=(
            ('post','/api/backup',{}),
            ('post','/api/ingest',{}),
            ('post','/api/reconcile',{}),
            ('post','/api/thresholds',{}),
            ('patch','/api/trades/1',{'comment':'proxy must not grant writes'}),
            ('post','/api/notes',{'text':'blocked'}),
            ('post','/api/comments',{'kind':'INTENT','target_type':'session','target_id':'2026-08-20','body':'blocked'}),
            ('post','/api/restore',{'name':'arena_fake.db'}),
        )
        with mock.patch.object(app,'ENVIRONMENT','production'), mock.patch.object(app,'PROCESS_ROLE','web'):
            for method,path,payload in attempts:
                response=getattr(client,method)(
                    path,json=payload,environ_base={'REMOTE_ADDR':'127.0.0.1'})
                self.assertEqual(response.status_code,403,(method,path,response.get_data(as_text=True)))
                self.assertEqual((response.get_json() or {}).get('error'),'production monitor is read-only')

    def test_production_web_blocks_full_database_export(self):
        with mock.patch.object(app,'ENVIRONMENT','production'), mock.patch.object(app,'PROCESS_ROLE','web'):
            response=app.app.test_client().get(
                '/api/export',environ_base={'REMOTE_ADDR':'127.0.0.1'})
        self.assertEqual(response.status_code,403)
        self.assertIn('unavailable',(response.get_json() or {}).get('error',''))

    def test_api_responses_receive_baseline_security_headers(self):
        response=app.app.test_client().get('/api/status')
        self.assertEqual(response.headers.get('Cache-Control'),'no-store, max-age=0')
        self.assertEqual(response.headers.get('X-Content-Type-Options'),'nosniff')
        self.assertEqual(response.headers.get('X-Frame-Options'),'DENY')
        self.assertEqual(response.headers.get('Referrer-Policy'),'strict-origin-when-cross-origin')
        self.assertIn('geolocation=()',response.headers.get('Permissions-Policy',''))
        self.assertIn("script-src 'self'",response.headers.get('Content-Security-Policy-Report-Only',''))

    def test_authenticated_desk_is_not_cached_persistently(self):
        response=app.app.test_client().get('/')
        self.assertEqual(response.headers.get('Cache-Control'),'no-store, max-age=0')
        html=response.get_data(as_text=True)
        self.assertIn("sessionStorage.setItem(DESK_CACHE_KEY",html)
        self.assertIn("localStorage.removeItem('ashDeskCache')",html)
        self.assertNotIn("localStorage.setItem('ashDeskCache'",html)

    def test_journal_escapes_stored_debrief_html(self):
        con=app.db()
        con.execute("INSERT INTO debriefs(ts,trade_date,q1,q2,q3) VALUES(?,?,?,?,?)",
                    ('2026-08-20T16:00:00-04:00','2026-08-20','<img src=x onerror=alert(1)>','',''))
        con.commit(); con.close()
        body=app.app.test_client().get('/api/journal?date=2026-08-20').get_data(as_text=True)
        self.assertNotIn('<img src=x',body)
        self.assertIn('&lt;img src=x',body)

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

    def _wipe_signals(self):
        con=app.db(); con.execute('DELETE FROM signals'); con.commit(); con.close()

    def _bar(self, hm, c):
        hh,mm=map(int, hm.split(':'))
        t=app.datetime(2026,8,19,hh,mm,tzinfo=app.NY).isoformat()
        return {'t':t,'o':c,'h':c,'l':c,'c':c,'v':1}

    def _orb_state(self, **kw):
        st={'c':102.0,'or_high':100.0,'or_low':98.0,'or_width_pct':1.0,'rvol':1.5,'bars':40,
            'or_outside_at_open':False,'or_first_break':'10:12','or_held_break':False,
            'prev_close':99.0,'gap_pct':0.01}
        st.update(kw)
        return st

    def test_dnt_skips_thin_session_inside_opn_osf(self):
        wide={'bid':545.82,'ask':550.0,'last':547.39}
        s={'bars':22,'c':547.0,'session_pct':0.95,'quote':wide,'sym':'META'}
        self.assertNotIn('thin session', app.do_not_trade_reasons(s, wide, sleeve='OPN'))
        self.assertNotIn('thin session', app.do_not_trade_reasons(s, wide, sleeve=['OSF']))
        self.assertIn('thin session', app.do_not_trade_reasons(s, wide, sleeve='ORB'))
        self.assertNotIn('wide underlying spread', app.do_not_trade_reasons(s, wide, sleeve='ORB'))
        self.assertNotIn('quote/tape divergence', app.do_not_trade_reasons({**s,'c':547.0}, {'last':540.0}, sleeve='ORB'))

    def test_skip_dnt_is_retryable_entry_is_not(self):
        self._wipe_signals()
        con=app.db()
        con.execute("""INSERT INTO signals(ts,trade_date,strategy_id,ticker,direction,score,details,execution_status)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    ('2026-08-19T09:51:00-04:00','2026-08-19','OSF','NVDA','PUT',1,'{}','SKIP_DNT'))
        con.execute("""INSERT INTO signals(ts,trade_date,strategy_id,ticker,direction,score,details,execution_status)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    ('2026-08-19T10:12:00-04:00','2026-08-19','ORB','QQQ','PUT',1,'{}','ENTRY_SUBMITTED'))
        con.commit(); con.close()
        self.assertFalse(app.already_signaled('2026-08-19','OSF','NVDA'))
        self.assertTrue(app.already_signaled('2026-08-19','ORB','QQQ'))

    def test_daily_cap_counts_open_risk_not_scratches(self):
        self._wipe_trades()
        frozen=app.datetime(2026,8,19,10,38,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,status,trade_date,signal_ts,pnl)
                       VALUES('ORB','QQQ','PUT','CLOSED','2026-08-19','2026-08-19T10:12:00-04:00',-75)""")
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,status,trade_date,signal_ts)
                       VALUES('ORB','TSLA','CALL','OPEN','2026-08-19','2026-08-19T10:28:00-04:00')""")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen):
            self.assertEqual(app.daily_fire_count('ORB','2026-08-19'),1)
            self.assertEqual(app.cluster_count('2026-08-19',20),1)
        self.assertTrue(app.loser_cooldown('ORB','2026-08-19','QQQ'))
        self.assertFalse(app.loser_cooldown('ORB','2026-08-19','SPY'))

    def test_orb_requires_three_closes_still_outside(self):
        orh,orl=100.0,98.0
        poke=[self._bar('09:50',99), self._bar('10:11',97.5), self._bar('10:12',99)]
        self.assertIsNone(app.opening_range_held(poke,orh,orl)[0])
        held=[self._bar('09:50',99), self._bar('10:11',97.4), self._bar('10:12',97.2), self._bar('10:13',97.0)]
        self.assertEqual(app.opening_range_held(held,orh,orl),('PUT',3))
        faded=held+[self._bar('10:14',98.5)]
        self.assertIsNone(app.opening_range_held(faded,orh,orl)[0])

    def test_midday_orb_misses_one_bar_poke(self):
        frozen=app.datetime(2026,8,19,10,15,tzinfo=app.NY)
        states={'QQQ':self._orb_state(c=97.0, or_held_break=False)}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            sigs,evals,_=app.midday_signals(states,'ORB')
        self.assertEqual(sigs,[])
        miss=next(x for x in evals if x['ticker']=='QQQ')
        self.assertEqual(miss['eligible'],0)
        self.assertIn('not held', miss['reason'])

    def test_midday_orb_fires_held_break(self):
        frozen=app.datetime(2026,8,19,10,15,tzinfo=app.NY)
        states={'QQQ':self._orb_state(c=97.0, or_held_break=True, or_held_bars=3)}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            sigs,_,_=app.midday_signals(states,'ORB')
        self.assertEqual(len(sigs),1)
        self.assertEqual(sigs[0]['direction'],'PUT')

    def test_dnt_still_blocks_halt_earnings_and_incomplete_tape(self):
        s={'bars':22,'c':100.0,'session_pct':0.5,'halt':True,'sym':'NVDA'}
        with mock.patch.object(app,'earnings_block',return_value='earnings 2026-08-19'):
            r=app.do_not_trade_reasons(s, sleeve='OPN')
        self.assertIn('incomplete tape', r)
        self.assertIn('halt / no prints', r)
        self.assertIn('earnings 2026-08-19', r)
        self.assertNotIn('thin session', r)

    def test_overnight_sleeve_still_sees_thin_session(self):
        s={'bars':20,'c':100.0,'session_pct':1.0,'sym':'SPY'}
        self.assertIn('thin session', app.do_not_trade_reasons(s, sleeve='CEG'))

    def test_orb_held_ignores_premarket_and_side_flips(self):
        orh,orl=100.0,98.0
        pre=[self._bar('09:31',97.0), self._bar('09:45',96.5), self._bar('09:59',97.2)]
        self.assertIsNone(app.opening_range_held(pre,orh,orl)[0])
        two=[self._bar('10:11',97.0), self._bar('10:12',96.8)]
        self.assertIsNone(app.opening_range_held(two,orh,orl)[0])
        flip=[self._bar('10:11',97.0), self._bar('10:12',101.0), self._bar('10:13',97.0)]
        self.assertIsNone(app.opening_range_held(flip,orh,orl)[0])
        call3=[self._bar('10:11',101.0), self._bar('10:12',101.2), self._bar('10:13',101.4)]
        self.assertEqual(app.opening_range_held(call3,orh,orl),('CALL',3))
        then_in=call3+[self._bar('10:14',99.0)]
        self.assertIsNone(app.opening_range_held(then_in,orh,orl)[0])

    def test_retryable_skips_include_cap_stale_opposite_not_loser(self):
        self._wipe_signals()
        con=app.db()
        for st,tk in (('SKIP_DAILY_CAP','SPY'),('SKIP_STALE_QUOTE','MSFT'),('SKIP_CLUSTER','AMD'),
                      ('SKIP_OPPOSITE','AMZN'),('SKIP_LOSER','AAPL'),('SKIP_GUEST','NVDA')):
            con.execute("""INSERT INTO signals(ts,trade_date,strategy_id,ticker,direction,execution_status)
                           VALUES(?,?,?,?,?,?)""",
                        ('2026-08-19T10:38:00-04:00','2026-08-19','ORB',tk,'CALL',st))
        con.commit(); con.close()
        self.assertFalse(app.already_signaled('2026-08-19','ORB','SPY'))
        self.assertFalse(app.already_signaled('2026-08-19','ORB','MSFT'))
        self.assertFalse(app.already_signaled('2026-08-19','ORB','AMD'))
        self.assertFalse(app.already_signaled('2026-08-19','ORB','AMZN'))
        self.assertFalse(app.already_signaled('2026-08-19','ORB','NVDA'))
        self.assertTrue(app.already_signaled('2026-08-19','ORB','AAPL'))

    def test_three_open_orbs_cap_fourth_then_retry_after_scratch(self):
        self._paper_cfg(); self._wipe_trades()
        frozen=app.datetime(2026,8,19,10,38,tzinfo=app.NY)
        con=app.db()
        for tk in ('QQQ','IWM','TSLA'):
            con.execute("""INSERT INTO trades(strategy_id,ticker,direction,status,trade_date,signal_ts)
                           VALUES('ORB',?,'PUT','OPEN','2026-08-19','2026-08-19T10:12:00-04:00')""",(tk,))
        con.commit(); con.close()
        states={'SPY':{'c':770.0,'bars':60,'session_pct':0.97,'quote':{'bid':770,'ask':770.02,'last':770.01}}}
        sig={'strategy_id':'ORB','ticker':'SPY','direction':'CALL','horizon':'EOD','window':'10:38'}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            status,_=self._submit(sig,states)
        self.assertEqual(status,'SKIP_DAILY_CAP')
        con=app.db()
        con.execute("UPDATE trades SET status='CLOSED',pnl=-75 WHERE ticker='QQQ'")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen):
            self.assertEqual(app.daily_fire_count('ORB','2026-08-19'),2)
            status,_=self._submit(sig,states)
        self.assertEqual(status,'ENTRY_SUBMITTED')

    def test_submit_opn_with_22_bars_and_iex_junk_is_not_dnt(self):
        self._paper_cfg(); self._wipe_trades()
        frozen=app.datetime(2026,8,19,9,51,tzinfo=app.NY)
        states={'IWM':{'c':302.22,'bars':22,'session_pct':0.95,'sym':'IWM',
                       'quote':{'bid':302.46,'ask':302.49,'last':302.47}}}
        sig={'strategy_id':'OPN','ticker':'IWM','direction':'CALL','horizon':'EOD','window':'09:51'}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            status,extra=self._submit(sig,states)
        self.assertEqual(status,'ENTRY_SUBMITTED')
        self.assertEqual(extra.get('dnt') or [], [])

    def test_submit_orb_meta_iex_spread_is_not_dnt(self):
        self._paper_cfg(); self._wipe_trades()
        frozen=app.datetime(2026,8,19,10,14,tzinfo=app.NY)
        states={'META':{'c':546.52,'bars':44,'session_pct':0.97,'sym':'META',
                        'quote':{'bid':545.82,'ask':550.0,'last':547.39}}}
        sig={'strategy_id':'ORB','ticker':'META','direction':'CALL','horizon':'EOD','window':'10:14'}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            status,extra=self._submit(sig,states)
        self.assertEqual(status,'ENTRY_SUBMITTED')
        self.assertEqual(extra.get('dnt') or [], [])

    def test_loser_on_qqq_does_not_block_spy_submit(self):
        self._paper_cfg(); self._wipe_trades()
        frozen=app.datetime(2026,8,19,10,38,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,status,trade_date,signal_ts,pnl)
                       VALUES('ORB','QQQ','PUT','CLOSED','2026-08-19','2026-08-19T10:12:00-04:00',-75)""")
        con.commit(); con.close()
        states={'SPY':{'c':770.0,'bars':60,'session_pct':0.97}}
        sig={'strategy_id':'ORB','ticker':'SPY','direction':'CALL','horizon':'EOD','window':'10:38'}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            status,_=self._submit(sig,states)
        self.assertEqual(status,'ENTRY_SUBMITTED')

    def test_replay_aug19_orb_tape_rejects_pokes_holds_tsla(self):
        book=app.ROOT/'data'/'development'/'arena.db'
        if not book.exists():
            self.skipTest('development arena.db not present')
        import sqlite3
        from datetime import datetime
        NY=app.NY
        con=sqlite3.connect(f'file:{book}?mode=ro', uri=True)
        con.row_factory=sqlite3.Row

        def rth_of(tk):
            rows=con.execute("""SELECT t,o,h,l,c,v FROM live_bars
                                WHERE ticker=? AND trade_date='2026-08-19' AND timeframe='1Min' ORDER BY t""",(tk,)).fetchall()
            return app.rth_bars([dict(x) for x in rows])

        def held_at(rth, orh, orl, cutoff):
            slice_=[]
            last=None
            for b in rth:
                hm=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY).strftime('%H:%M')
                if hm>cutoff: break
                slice_.append(b); last=(hm,float(b['c']))
            side,n=app.opening_range_held(slice_, orh, orl)
            return side,n,last

        first_held={}
        at_fill={}
        for tk in ('QQQ','IWM','TSLA','META','MSFT','SPY'):
            rth=rth_of(tk)
            orh,orl,_=app.opening_range(rth)
            hit=None
            for i,b in enumerate(rth):
                hm=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY).strftime('%H:%M')
                if hm<'10:05' or hm>'10:38': continue
                side,n=app.opening_range_held(rth[:i+1], orh, orl)
                if side and hit is None:
                    hit=(hm,side,n,float(b['c']),orh,orl)
            first_held[tk]=hit
            at_fill[tk]=(orh,orl)+held_at(rth,orh,orl,'10:12' if tk!='TSLA' else '10:28')
        con.close()

        self.assertIsNone(first_held['QQQ'], msg=first_held)
        self.assertIsNone(at_fill['QQQ'][2])
        self.assertIsNone(at_fill['IWM'][2], msg='IWM 10:12 fill was a one-bar poke')
        self.assertEqual(first_held['IWM'][0],'10:15', msg=first_held)
        self.assertIsNone(at_fill['TSLA'][2], msg='TSLA 10:28 fill was only two closes outside')
        self.assertEqual(first_held['TSLA'][0],'10:29', msg=first_held)
        self.assertEqual(first_held['TSLA'][1],'CALL')
        self.assertEqual(first_held['META'][0],'10:17', msg=first_held)
        self.assertEqual(first_held['MSFT'][0],'10:19', msg=first_held)
        self.assertIsNone(first_held['SPY'], msg=first_held)
        iwm=first_held['IWM']
        self.assertLess(abs(app.opening_range_excursion(iwm[3],iwm[4],iwm[5])),0.0015)
        tsla=first_held['TSLA']
        self.assertGreater(abs(app.opening_range_excursion(tsla[3],tsla[4],tsla[5])),0.0015)

    def test_orb_shallow_hold_does_not_fire(self):
        frozen=app.datetime(2026,8,19,10,15,tzinfo=app.NY)
        states={'IWM':self._orb_state(c=301.55, or_high=303.13, or_low=301.76,
                                     or_held_break=True, or_held_bars=3, bars=40, rvol=1.7)}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            sigs,evals,_=app.midday_signals(states,'ORB')
        self.assertEqual(sigs,[])
        miss=next(x for x in evals if x['ticker']=='IWM')
        self.assertIn('shallow', miss['reason'])

    def test_orb_deep_held_break_still_fires(self):
        frozen=app.datetime(2026,8,19,10,29,tzinfo=app.NY)
        states={'TSLA':self._orb_state(c=342.275, or_high=341.14, or_low=335.745,
                                      or_held_break=True, or_held_bars=3, bars=50, rvol=1.8)}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            sigs,_,_=app.midday_signals(states,'ORB')
        self.assertEqual(len(sigs),1)
        self.assertEqual(sigs[0]['ticker'],'TSLA')
        self.assertEqual(sigs[0]['direction'],'CALL')

    def test_one_lot_does_not_scale_to_flat(self):
        self._wipe_trades()
        frozen=app.datetime(2026,8,19,10,32,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,status,trade_date,
                       entry_filled_at,horizon,atm_spot)
                       VALUES(1,'ORB','TSLA','CALL','TSLA260819C00340000',1,'OPEN','2026-08-19',
                       '2026-08-19T10:28:00-04:00','EOD',341.0)""")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'mae_mfe_from_tape',return_value=(0.0,0.01)), \
             mock.patch.object(app,'submit_exit') as ex, \
             mock.patch.object(app,'local_intraday_state',return_value={'c':343.0,'or_high':341.14,'or_low':335.7}):
            app.refresh_excursions_and_stops()
        ex.assert_not_called()
        con=app.db(); row=con.execute('SELECT status FROM trades WHERE id=1').fetchone(); con.close()
        self.assertEqual(row['status'],'OPEN')

    def test_option_pnl_rounds_to_cents(self):
        self.assertEqual(app.option_pnl(1.6,0.96,1),-64.0)
        self.assertEqual(app.option_pnl(5.7,3.6,1),-210.0)

    def test_fresh_pending_locks_stale_pending_retries(self):
        self._wipe_signals()
        frozen=app.datetime(2026,8,19,10,20,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO signals(ts,trade_date,strategy_id,ticker,direction,execution_status)
                       VALUES(?,?,?,?,?,?)""",
                    ('2026-08-19T10:19:00-04:00','2026-08-19','ORB','QQQ','PUT','PENDING'))
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen):
            self.assertTrue(app.already_signaled('2026-08-19','ORB','QQQ'))
        stale=app.datetime(2026,8,19,10,25,tzinfo=app.NY)
        with mock.patch.object(app,'now_ny',return_value=stale):
            self.assertFalse(app.already_signaled('2026-08-19','ORB','QQQ'))

    def test_upsert_pending_reuses_skip_dnt_row(self):
        self._wipe_signals()
        frozen=app.datetime(2026,8,19,9,55,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO signals(ts,trade_date,strategy_id,ticker,direction,score,details,execution_status)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    ('2026-08-19T09:51:00-04:00','2026-08-19','OSF','NVDA','PUT',1,'{}','SKIP_DNT'))
        con.commit(); con.close()
        sig={'strategy_id':'OSF','ticker':'NVDA','direction':'PUT','score':1.2,'details':{'clock':'09:55'},
             'window':'09:55','horizon':'EOD'}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            app._upsert_pending_signal('2026-08-19',sig)
        con=app.db()
        n=con.execute("SELECT COUNT(*) n FROM signals WHERE trade_date='2026-08-19' AND strategy_id='OSF' AND ticker='NVDA'").fetchone()['n']
        st=con.execute("SELECT execution_status FROM signals WHERE trade_date='2026-08-19' AND strategy_id='OSF' AND ticker='NVDA'").fetchone()['execution_status']
        con.close()
        self.assertEqual(n,1)
        self.assertEqual(st,'PENDING')

    def test_transient_exit_error_keeps_broker_note(self):
        self._wipe_trades()
        frozen=app.datetime(2026,8,19,15,55,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,status,trade_date,
                       exit_due_date,horizon,broker_note)
                       VALUES(1,'ORB','QQQ','PUT','QQQ260819P00713000',1,'OPEN','2026-08-19',
                       '2026-08-19','EOD','paper market order')""")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'submit_exit',side_effect=BrokenPipeError('[Errno 32] Broken pipe')):
            app.submit_due_exits()
        con=app.db(); row=con.execute('SELECT broker_note,status FROM trades WHERE id=1').fetchone(); con.close()
        self.assertEqual(row['status'],'OPEN')
        self.assertEqual(row['broker_note'],'paper market order')

    def _submit(self, sig, states):
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        app.CFG.write_text(json.dumps({
            'alpaca_key':'k','alpaca_secret':'s','fred_key':'f','keys_ok':True,
            'broker_orders_enabled':True,'max_daily_fires':3,'max_cluster':5,
        }))
        spot=states[sig['ticker']]['c']
        opt=f"{sig['ticker']}260819C00001000"
        with mock.patch.object(app,'option_contract',return_value=(opt,'2026-08-19',spot,'0dte atm',{'dte':'0dte','moneyness':'atm'})), \
             mock.patch.object(app,'option_quote',return_value={'bid':1.0,'ask':1.05,'spread':0.05,'age_sec':1}), \
             mock.patch.object(app,'pdt_block',return_value=None), \
             mock.patch.object(app,'session_coverage',return_value={sig['ticker']:{'pct':0.97}}), \
             mock.patch.object(app,'place_broker_order',return_value={'id':'ord-test'}), \
             mock.patch.object(app,'greeks_snap',return_value={'iv':0.2,'delta':0.5,'gamma':0.1}), \
             mock.patch.object(app,'log_contract'), \
             mock.patch.object(app,'log_shadow'), \
             mock.patch.object(app,'event'):
            return app.submit_entry(sig, states)


if __name__=='__main__':
    unittest.main()
