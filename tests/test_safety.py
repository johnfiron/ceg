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

    def test_entry_interlock_is_separate_from_risk_reducing_orders(self):
        app.CFG.write_text(json.dumps({
            'broker_orders_enabled':True,
            'new_entries_enabled':False,
        }))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        self.assertTrue(app.broker_orders_enabled())
        self.assertFalse(app.new_entries_enabled())
        with mock.patch.object(app,'postj',return_value={'id':'sell-ok'}):
            order=app.place_broker_order({
                'client_order_id':'x53-1','symbol':'SPY260826C00700000',
                'qty':'1','side':'sell','type':'market','time_in_force':'day',
            })
        self.assertEqual(order['id'],'sell-ok')

    def test_buy_order_rechecks_entry_pause_at_submission_boundary(self):
        app.CFG.write_text(json.dumps({
            'broker_orders_enabled':True,
            'new_entries_enabled':False,
        }))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        payload={'client_order_id':'a53-20260826-opn-spy','symbol':'SPY260826C00700000',
                 'qty':'1','side':'buy','type':'market','time_in_force':'day'}
        with mock.patch.object(app,'broker_order_by_client_id',return_value=None), \
             mock.patch.object(app,'postj') as post:
            with self.assertRaisesRegex(RuntimeError,'paused'):
                app.place_broker_order(payload)
        post.assert_not_called()

    def test_alpaca_nanosecond_timestamp_is_fresh(self):
        frozen=app.datetime(2026,8,26,9,51,20,tzinfo=app.NY)
        parsed=app.parse_ny('2026-08-26T13:51:19.013472866Z')
        self.assertEqual(parsed.microsecond,13472)
        with mock.patch.object(app,'now_ny',return_value=frozen):
            age=(app.now_ny()-parsed).total_seconds()
        self.assertLess(age,2)

    def test_broker_endpoint_is_permanently_paper_only(self):
        self.assertEqual(app.paper_api_url('/account'),'https://paper-api.alpaca.markets/v2/account')
        with mock.patch.object(app,'PAPER','https://api.alpaca.markets/v2'):
            with self.assertRaisesRegex(RuntimeError,'non-paper'):
                app.paper_api_url('/orders')

    def test_expanded_reading_universe_stays_out_of_execution_and_maps_news(self):
        self.assertTrue({'AVGO','GOOGL','NFLX','JPM','BAC','XOM','COIN','PLTR','SMH','DIA'}.issubset(app.ALL_TICKERS))
        self.assertTrue(set(app.READING_TICKERS).isdisjoint(app.MIDDAY_TICKERS))
        payload={'news':[
            {'headline':'Chip headline','summary':'Context','source':'wire','url':'https://example.test/1',
             'created_at':'2026-08-24T12:00:00Z','symbols':['AVGO','SMH']},
            {'headline':'Older headline','source':'wire','symbols':['AVGO']},
        ]}
        with mock.patch.object(app,'cache_get',return_value=None), \
             mock.patch.object(app,'cache_set') as store, \
             mock.patch.object(app,'getj',return_value=payload) as fetch:
            rows=app.latest_stock_news(['AVGO','SMH'])
        self.assertEqual(rows['AVGO']['headline'],'Chip headline')
        self.assertEqual(rows['SMH']['source'],'wire')
        self.assertIn('/v1beta1/news',fetch.call_args.args[0])
        store.assert_called_once()
        response=app.app.test_client().get('/api/news?symbols=NOTREAL')
        self.assertEqual(response.status_code,400)

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

    def test_production_web_opens_the_desk_without_local_keys(self):
        app.CFG.write_text(json.dumps({'keys_ok':False,'broker_orders_enabled':False}))
        with mock.patch.object(app,'ENVIRONMENT','production'), mock.patch.object(app,'PROCESS_ROLE','web'):
            self.assertFalse(app.keys_ok())
            self.assertTrue(app.desk_configured())
            response=app.app.test_client().get('/api/status')
        self.assertTrue((response.get_json() or {}).get('configured'))

    def test_order_retry_recovers_deterministic_client_id(self):
        app.CFG.write_text(json.dumps({'broker_orders_enabled':True,'new_entries_enabled':True}))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        expected={'id':'existing','client_order_id':'a53-20260818-ceg-spy'}
        with mock.patch.object(app,'broker_order_by_client_id',side_effect=[None,expected]), \
             mock.patch.object(app,'postj',side_effect=RuntimeError('lost response')) as post:
            got=app.place_broker_order({'client_order_id':expected['client_order_id'],'symbol':'SPY','qty':'1'})
        self.assertEqual(got,expected)
        post.assert_called_once()

    def test_lost_buy_response_is_reported_as_ambiguous(self):
        app.CFG.write_text(json.dumps({'broker_orders_enabled':True,'new_entries_enabled':True}))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        payload={'client_order_id':'a53-20260826-opn-spy','symbol':'SPY260826C00700000',
                 'qty':'1','side':'buy','type':'market','time_in_force':'day'}
        with mock.patch.object(app,'broker_order_by_client_id',return_value=None), \
             mock.patch.object(app,'postj',side_effect=TimeoutError('response lost')):
            with self.assertRaises(app.AmbiguousBrokerOrder):
                app.place_broker_order(payload)

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
        self.assertIn('let raw=await r.text()',html)
        self.assertIn("catch(e){$('setupMsg').textContent=e.message||String(e)}",html)
        self.assertIn('function applyMonitorLock(s)',html)
        self.assertIn("const FROM_VAULT=INTRO_Q.get('from')==='vault'",html)
        self.assertIn("INTRO_Q.get('intro')==='skip'",html)
        self.assertIn('function finishIntroImmediate()',html)
        self.assertIn('if(SKIP_INTRO)finishIntroImmediate()',html)
        self.assertIn('if(ASH_BASE||FROM_VAULT)applyMonitorLock',html)
        self.assertIn('href="manifest.webmanifest"',html)
        self.assertIn('function stepInspect(delta)',html)
        self.assertIn("timeZone:'America/New_York'",html)
        self.assertIn("document.body.classList.toggle('monitor-lock'",html)
        self.assertNotIn("[{date:null,cumPnl:0}]",html)
        self.assertIn("api('/api/sleeve_history?days=30'",html)
        self.assertIn("api(`/api/live_bars/${ticker}`",html)
        self.assertIn("s.filter(x=>(x.closed||0)>0)",html)
        self.assertIn('id="heroChart"',html)
        self.assertIn('id="inspectChart"',html)
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

    def test_ledger_repair_pairs_uuid_liquidation(self):
        self._wipe_trades()
        con=app.db()
        con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,
                       expiry,entry_order_id,entry_client_id,entry_fill,entry_filled_at,exit_due_date,status,pnl,exit_kind)
                       VALUES(25,'OPN','IWM','PUT','IWM260820P00300000',1,'2026-08-20T13:51:15Z','2026-08-20','2026-08-20',
                       'buy25','a53-20260820-opn-iwm',0.83,'2026-08-20T13:51:15Z','2026-08-20','CLOSED',-83,'EXPIRED')""")
        con.commit(); con.close()
        sell={'id':'liq25','client_order_id':'21b17cf4-8dbf-4dac-867b-d36d27ffa9c8','side':'sell','status':'filled',
              'symbol':'IWM260820P00300000','qty':'1','filled_qty':'1','filled_avg_price':'2.36',
              'filled_at':'2026-08-20T19:45:06Z'}
        plan=app.broker_ledger_repair_plan([sell])
        self.assertEqual([(x['trade_id'],x['exit_order_id'],x['pnl']) for x in plan],[(25,'liq25',153.0)])
        self.assertEqual(app.apply_broker_ledger_repair(plan),{'updated':1,'inserted':0})

    def test_ledger_repair_splits_qty2_uuid_sell_across_two_tickets(self):
        self._wipe_trades()
        con=app.db()
        for tid,fill,entered in ((37,0.82,'2026-08-21T14:17:16Z'),(38,1.03,'2026-08-21T14:30:22Z')):
            con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,
                           expiry,entry_order_id,entry_client_id,entry_fill,entry_filled_at,exit_due_date,status,pnl,exit_kind)
                           VALUES(?,'ORB','NVDA','PUT','NVDA260821P00215000',1,?,'2026-08-21','2026-08-21',
                           ?,?, ?,?,'2026-08-21','CLOSED',?,'EXPIRED')""",
                        (tid,entered,f'buy{tid}',f'a53-20260821-orb-nvda-{tid}',fill,entered,-fill*100))
        con.commit(); con.close()
        sell={'id':'liq37','client_order_id':'3ff746d8-0098-4b69-8792-99efdd1e6749','side':'sell','status':'filled',
              'symbol':'NVDA260821P00215000','qty':'2','filled_qty':'2','filled_avg_price':'0.31',
              'filled_at':'2026-08-21T19:30:47Z'}
        plan=app.broker_ledger_repair_plan([sell])
        self.assertEqual([(x['trade_id'],x['exit_order_id'],x['pnl']) for x in plan],
                         [(37,'liq37',-51.0),(38,'liq37',-72.0)])
        self.assertEqual(app.apply_broker_ledger_repair(plan),{'updated':2,'inserted':0})
        one_lot=dict(sell); one_lot['qty']='1'; one_lot['filled_qty']='1'; one_lot['id']='liq-one'
        self._wipe_trades()
        con=app.db()
        for tid,fill,entered in ((37,0.82,'2026-08-21T14:17:16Z'),(38,1.03,'2026-08-21T14:30:22Z')):
            con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,
                           expiry,entry_order_id,entry_client_id,entry_fill,entry_filled_at,exit_due_date,status,pnl,exit_kind)
                           VALUES(?,'ORB','NVDA','PUT','NVDA260821P00215000',1,?,'2026-08-21','2026-08-21',
                           ?,?, ?,?,'2026-08-21','CLOSED',?,'EXPIRED')""",
                        (tid,entered,f'buy{tid}',f'a53-20260821-orb-nvda-{tid}',fill,entered,-fill*100))
        con.commit(); con.close()
        plan=app.broker_ledger_repair_plan([one_lot])
        self.assertEqual([x['trade_id'] for x in plan],[37])

    def test_expire_dead_options_closes_from_uuid_sell_not_full_debit(self):
        self._wipe_trades()
        frozen=app.datetime(2026,8,21,16,30,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,
                       entry_fill,entry_filled_at,exit_due_date,status,horizon)
                       VALUES(35,'OSF','NVDA','PUT','NVDA260821P00217500',1,?,?,?,1.46,?,'2026-08-21','OPEN','EOD')""",
                    ('2026-08-21T09:51:00-04:00','2026-08-21','2026-08-21','2026-08-21T09:51:08Z'))
        con.commit(); con.close()
        sell={'id':'liq35','client_order_id':'a62df2ac-846d-420f-8c6a-912c299d8a03','side':'sell','status':'filled',
              'symbol':'NVDA260821P00217500','qty':'1','filled_qty':'1','filled_avg_price':'2.54',
              'filled_at':'2026-08-21T19:30:48Z'}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            app.expire_dead_options(held=set(), orders=[sell])
        con=app.db(); row=con.execute('SELECT status,pnl,exit_fill,exit_kind FROM trades WHERE id=35').fetchone(); con.close()
        self.assertEqual(row['status'],'CLOSED')
        self.assertEqual(row['exit_fill'],2.54)
        self.assertAlmostEqual(row['pnl'],108.0)
        self.assertNotEqual(row['exit_kind'],'EXPIRED')

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
        con=app.db()
        row=con.execute('SELECT id,strategy_id,ticker,status,pnl,exit_order_id FROM trades').fetchone()
        phases=[r['phase'] for r in con.execute('SELECT phase FROM trade_snapshots WHERE trade_id=? ORDER BY id',(row['id'],)).fetchall()]
        codes=[r['code'] for r in con.execute('SELECT code FROM trade_audit_events WHERE trade_id=? ORDER BY id',(row['id'],)).fetchall()]
        con.close()
        self.assertEqual((row['strategy_id'],row['ticker'],row['status'],row['pnl'],row['exit_order_id']),
                         ('ORB','IWM','CLOSED',-30.0,'sell1'))
        self.assertEqual(phases,['ENTRY','EXIT'])
        self.assertIn('TRADE_RECOVERED',codes)
        self.assertIn('EXIT_FILLED',codes)

    def test_ledger_repair_recovers_missing_uuid_liquidation_round_trip(self):
        self._wipe_trades()
        buy={'id':'buy1','client_order_id':'a53-20260820-opn-iwm','side':'buy','status':'filled',
             'symbol':'IWM260820P00300000','qty':'1','filled_qty':'1','filled_avg_price':'0.83',
             'submitted_at':'2026-08-20T13:51:15Z','filled_at':'2026-08-20T13:51:15Z'}
        sell={'id':'liq1','client_order_id':'21b17cf4-8dbf-4dac-867b-d36d27ffa9c8','side':'sell','status':'filled',
              'symbol':'IWM260820P00300000','qty':'1','filled_qty':'1','filled_avg_price':'2.36',
              'filled_at':'2026-08-20T19:45:06Z'}
        plan=app.broker_ledger_repair_plan([buy,sell])
        self.assertEqual([(x['action'],x['pnl'],x['exit_order_id']) for x in plan],
                         [('insert',153.0,'liq1')])

    def test_ledger_repair_uses_broker_expiration_evidence_only(self):
        self._wipe_trades()
        buy={'id':'buy1','client_order_id':'a53-mvr-qqq-1786984649','side':'buy','status':'filled',
             'symbol':'QQQ260817C00740000','qty':'1','filled_qty':'1','filled_avg_price':'0.02',
             'submitted_at':'2026-08-17T16:37:29Z','filled_at':'2026-08-17T16:37:29Z'}
        self.assertEqual(app.broker_ledger_repair_plan([buy]),[])
        expiry={'activity_type':'OPEXP','symbol':'QQQ260817C00740000','qty':'-1','date':'2026-08-18'}
        plan=app.broker_ledger_repair_plan([buy],[expiry])
        self.assertEqual([(x['action'],x['pnl'],x['exit_kind']) for x in plan],
                         [('insert',-2.0,'BROKER_EXPIRY')])
        self.assertEqual(app.apply_broker_ledger_repair(plan),{'updated':0,'inserted':1})
        con=app.db(); row=con.execute('SELECT status,pnl,exit_kind FROM trades').fetchone(); con.close()
        self.assertEqual((row['status'],row['pnl'],row['exit_kind']),('CLOSED',-2.0,'BROKER_EXPIRY'))

    def test_ledger_repair_corrects_expiry_from_same_symbol_generic_exit(self):
        self._wipe_trades()
        con=app.db()
        con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,
                       expiry,entry_order_id,entry_client_id,entry_fill,entry_filled_at,exit_due_date,status,pnl,exit_kind)
                       VALUES(11,'RSI2','QQQ','CALL','QQQ260820C00723000',1,'2026-08-19T19:45:17Z',
                       '2026-08-19','2026-08-20','buy11','a53-20260819-rsi2-qqq',0.45,
                       '2026-08-19T19:45:17Z','2026-08-20','CLOSED',-45,'EXPIRED')""")
        con.commit(); con.close()
        sell={'id':'sell24','client_order_id':'x53-24','side':'sell','status':'filled',
              'symbol':'QQQ260820C00723000','qty':'1','filled_qty':'1','filled_avg_price':'0.08',
              'filled_at':'2026-08-20T13:35:04Z'}
        plan=app.broker_ledger_repair_plan([sell])
        self.assertEqual([(x['trade_id'],x['pnl'],x['exit_order_id']) for x in plan],
                         [(11,-37.0,'sell24')])

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

    def _wipe_option_marks(self):
        con=app.db()
        con.execute('DELETE FROM option_mark_snapshots')
        con.execute("DELETE FROM meta WHERE k='positions_snapshot'")
        con.commit(); con.close()

    def test_position_snapshot_persists_linked_marks_without_same_cycle_duplicates(self):
        self._wipe_option_marks(); self._wipe_trades()
        frozen=app.datetime(2026,8,21,11,0,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,
                       trade_date,expiry,entry_fill,entry_filled_at,status)
                       VALUES('ORB','QQQ','CALL','QQQ260821C00570000',2,?,'2026-08-21',
                              '2026-08-21',1.0,?,'OPEN')""",
                    (frozen.isoformat(),frozen.isoformat()))
        tid=con.execute('SELECT last_insert_rowid() x').fetchone()['x']
        con.commit(); con.close()
        position={'symbol':'QQQ260821C00570000','qty':'2','side':'long','current_price':'1.50',
                  'market_value':'300','cost_basis':'200','unrealized_pl':'100',
                  'unrealized_plpc':'0.5','avg_entry_price':'1.0'}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            app.snapshot_positions([position])
            app.snapshot_positions([position])
        con=app.db()
        rows=con.execute('SELECT * FROM option_mark_snapshots WHERE trade_id=?',(tid,)).fetchall()
        indexes={r['name'] for r in con.execute("PRAGMA index_list('option_mark_snapshots')").fetchall()}
        con.close()
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['strategy_id'],rows[0]['option_symbol'],rows[0]['mark'],rows[0]['source']),
                         ('ORB','QQQ260821C00570000',1.5,'broker'))
        self.assertIn('idx_option_marks_ts',indexes)
        self.assertIn('idx_option_marks_sleeve',indexes)

    def test_current_snapshot_uses_current_session_for_overnight_position(self):
        self._wipe_option_marks(); self._wipe_trades()
        frozen=app.datetime(2026,8,21,11,0,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,trade_date,expiry,status)
                       VALUES('MACD','QQQ','CALL','QQQ260824C00570000',1,'2026-08-20','2026-08-24','OPEN')""")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'local_intraday_state',return_value={'c':570}) as state:
            app.snapshot_positions([{'symbol':'QQQ260824C00570000','qty':'1','current_price':'1.50'}])
        self.assertEqual(state.call_args.args,('QQQ','2026-08-21'))

    def test_option_mark_snapshot_retention_is_bounded(self):
        self._wipe_option_marks(); self._wipe_trades()
        frozen=app.datetime(2026,8,21,12,0,tzinfo=app.NY)
        old=(frozen-app.timedelta(days=app.OPTION_MARK_RETENTION_DAYS+1)).isoformat()
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,trade_date,status)
                       VALUES('MVR','SPY','PUT','SPY260821P00640000',1,'2026-08-21','OPEN')""")
        tid=con.execute('SELECT last_insert_rowid() x').fetchone()['x']
        con.execute("""INSERT INTO option_mark_snapshots(
                       ts,mark_ts,trade_date,trade_id,strategy_id,ticker,option_symbol,activity_qty,source)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (old,old,'2026-07-21',tid,'MVR','SPY','SPY260821P00640000',1,'broker'))
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen):
            app.snapshot_positions([{'symbol':'SPY260821P00640000','qty':'1','current_price':'0.75'}])
        con=app.db()
        rows=con.execute('SELECT ts FROM option_mark_snapshots WHERE trade_id=? ORDER BY ts',(tid,)).fetchall()
        con.close()
        self.assertEqual([r['ts'] for r in rows],[frozen.isoformat()])

    def test_sleeve_history_groups_contract_paths_fills_and_aggregate_pnl(self):
        self._wipe_option_marks(); self._wipe_trades()
        frozen=app.datetime(2026,8,21,13,0,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,
                       trade_date,expiry,entry_fill,entry_filled_at,status)
                       VALUES('ORB','QQQ','CALL','QQQ260821C00570000',2,?,'2026-08-21',
                              '2026-08-21',1.0,?,'OPEN')""",(frozen.isoformat(),frozen.isoformat()))
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,
                       trade_date,expiry,entry_fill,entry_filled_at,exit_fill,exit_filled_at,status,pnl)
                       VALUES('ORB','IWM','PUT','IWM260821P00300000',1,?,'2026-08-21',
                              '2026-08-21',0.8,?,1.05,?,'CLOSED',25)""",
                    (frozen.isoformat(),frozen.isoformat(),frozen.isoformat()))
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen):
            app.snapshot_positions([{'symbol':'QQQ260821C00570000','qty':'2','current_price':'1.5',
                                     'unrealized_pl':'100','unrealized_plpc':'0.5'}])
            response=app.app.test_client().get('/api/sleeve_history?days=1&end=2026-08-21')
        self.assertEqual(response.status_code,200)
        body=response.get_json()
        orb=next(x for x in body['strategies'] if x['strategy_id']=='ORB')
        self.assertEqual(orb['pnl'],{'realized':25.0,'unrealized':100.0,'total':125.0})
        self.assertEqual(len(orb['contracts']),2)
        opened=next(x for x in orb['contracts'] if x['status']=='OPEN')
        self.assertEqual(opened['quantity'],{'activity':2,'broker':2.0})
        self.assertEqual(opened['current_mark']['price'],1.5)
        self.assertEqual(opened['fills']['entry']['price'],1.0)
        self.assertEqual(len(opened['path']),1)
        client=app.app.test_client()
        self.assertEqual(client.get('/api/sleeve_history?days=31').status_code,400)
        self.assertEqual(client.get(
            '/api/sleeve_history?start=2026-07-01&end=2026-08-21').status_code,400)

    def test_position_fallback_and_production_history_read_use_runner_sqlite(self):
        self._wipe_option_marks(); self._wipe_trades()
        first=app.datetime(2026,8,21,13,30,tzinfo=app.NY)
        second=app.datetime(2026,8,21,13,31,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,trade_date,
                       entry_fill,entry_filled_at,status)
                       VALUES('MVR','SPY','PUT','SPY260821P00640000',1,'2026-08-21',0.5,?,'OPEN')""",
                    (first.isoformat(),))
        con.commit(); con.close()
        stored={'symbol':'SPY260821P00640000','qty':'1','current_price':'0.7','unrealized_pl':'20'}
        with mock.patch.object(app,'now_ny',return_value=first):
            app.snapshot_positions([stored])
        with mock.patch.object(app,'now_ny',return_value=second), \
             mock.patch.object(app,'broker_positions',side_effect=RuntimeError('paper API down')):
            fallback=app.snapshot_positions()
            positions=app.app.test_client().get('/api/positions').get_json()
        self.assertEqual(fallback[0]['symbol'],stored['symbol'])
        self.assertEqual(fallback[0]['current_price'],stored['current_price'])
        self.assertEqual(positions['source'],'runner_snapshot')
        self.assertEqual(positions['positions'][0]['current_price'],'0.7')
        with mock.patch.object(app,'ENVIRONMENT','production'), \
             mock.patch.object(app,'PROCESS_ROLE','web'), \
             mock.patch.object(app,'broker_positions',side_effect=AssertionError('web touched broker')):
            response=app.app.test_client().get('/api/sleeve_history?days=1&end=2026-08-21')
        self.assertEqual(response.status_code,200)
        contract=response.get_json()['strategies'][0]['contracts'][0]
        self.assertEqual(contract['current_mark']['source'],'stored')
        self.assertEqual(contract['current_mark']['mark_at'],first.isoformat())

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

    def test_option_candidates_capture_quotes_volume_oi_and_component_grades(self):
        frozen=app.datetime(2026,8,19,11,0,tzinfo=app.NY)
        symbol='META260819C00100000'
        payload={'option_contracts':[{
            'symbol':symbol,'expiration_date':'2026-08-19','strike_price':'100','open_interest':321,
        }]}
        quote={symbol:{'bid':1.0,'ask':1.08,'spread':.08,'ts':frozen.isoformat(),'age_sec':0}}
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'getj',return_value=payload), \
             mock.patch.object(app,'ah',return_value={}), \
             mock.patch.object(app,'option_quotes',return_value=quote), \
             mock.patch.object(app,'option_latest_volumes',return_value={symbol:456}):
            _,_,_,_,style=app.option_contract(
                'META','CALL',100,allow_0dte=True,style={'dte':'0dte','moneyness':'atm'})
        candidate=style['_candidates'][0]
        self.assertEqual((candidate['bid'],candidate['ask'],candidate['spread']),(1.0,1.08,.08))
        self.assertEqual((candidate['volume'],candidate['open_interest']),(456,321))
        self.assertEqual(candidate['components']['grades']['freshness']['grade'],'A')
        self.assertEqual(style['_selected_quote']['volume'],456)

    def test_contract_quality_tie_keeps_exact_target(self):
        frozen=app.datetime(2026,8,19,11,0,tzinfo=app.NY)
        exact='META260819C00100000'; farther='META260819C00101000'
        payload={'option_contracts':[
            {'symbol':exact,'expiration_date':'2026-08-19','strike_price':'100','open_interest':500},
            {'symbol':farther,'expiration_date':'2026-08-19','strike_price':'101','open_interest':500},
        ]}
        quotes={s:{'bid':1.0,'ask':1.05,'spread':.05,'ts':frozen.isoformat(),'age_sec':0} for s in (exact,farther)}
        quality={'score':75,'grade':'B','components':{},'quote':{}}
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'getj',return_value=payload), \
             mock.patch.object(app,'ah',return_value={}), \
             mock.patch.object(app,'option_quotes',return_value=quotes), \
             mock.patch.object(app,'option_latest_volumes',return_value={exact:500,farther:500}), \
             mock.patch.object(app,'greeks_snap',return_value={'delta':.5}), \
             mock.patch.object(app,'contract_quality',return_value=quality):
            symbol,_,_,_,_=app.option_contract(
                'META','CALL',100,allow_0dte=True,style={'dte':'0dte','moneyness':'atm'})
        self.assertEqual(symbol,exact)

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

    def test_daily_cap_counts_closed_trades_but_cluster_stays_time_bounded(self):
        self._wipe_trades()
        frozen=app.datetime(2026,8,19,10,38,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,status,trade_date,signal_ts,pnl)
                       VALUES('ORB','QQQ','PUT','CLOSED','2026-08-19','2026-08-19T10:12:00-04:00',-75)""")
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,status,trade_date,signal_ts)
                       VALUES('ORB','TSLA','CALL','OPEN','2026-08-19','2026-08-19T10:28:00-04:00')""")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen):
            self.assertEqual(app.daily_fire_count('ORB','2026-08-19'),2)
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

    def test_daily_cap_remains_consumed_after_a_trade_closes(self):
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
            self.assertEqual(app.daily_fire_count('ORB','2026-08-19'),3)
            status,_=self._submit(sig,states)
        self.assertEqual(status,'SKIP_DAILY_CAP')

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

    def test_premium_loss_boundary_exits_one_lot(self):
        self._wipe_trades()
        frozen=app.datetime(2026,8,19,10,20,tzinfo=app.NY)
        con=app.db()
        con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,status,trade_date,
                       entry_fill,entry_filled_at,horizon,atm_spot)
                       VALUES(1,'MVR','QQQ','CALL','QQQ260819C00710000',1,'OPEN','2026-08-19',
                       2.0,'2026-08-19T10:00:00-04:00','EOD',710.0)""")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'mae_mfe_from_tape',return_value=(-0.005,0.002)), \
             mock.patch.object(app,'option_quote',return_value={'bid':1.1,'ask':1.2,'age_sec':1}), \
             mock.patch.object(app,'local_intraday_state',return_value={'c':706.0,'vwap_dist_atr':-1.0}), \
             mock.patch.object(app,'submit_exit') as ex:
            app.refresh_excursions_and_stops()
        self.assertEqual(ex.call_args.args[1],'RISK')

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

    def test_canonical_trade_schema_migrates_without_replacing_activity(self):
        con=app.db()
        names={r['name'] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'trade_%'").fetchall()}
        trade_cols={r['name'] for r in con.execute('PRAGMA table_info(trades)').fetchall()}
        con.close()
        self.assertTrue({'trade_snapshots','trade_predictions','trade_candidates','trade_audit_events'}<=names)
        self.assertTrue({'origin','strategy_version','parameter_hash','fees','slippage','modeled_slippage',
                         'actual_slippage','costs_source','exit_bid','exit_ask','exit_spread'}<=trade_cols)

    def test_occ_identity_and_option_value_state_are_deterministic(self):
        parsed=app.parse_occ_symbol('QQQ260824P00707000')
        self.assertEqual((parsed['underlying'],parsed['type'],parsed['strike'],parsed['expiry']),
                         ('QQQ','PUT',707.0,'2026-08-24'))
        self.assertFalse(app.parse_occ_symbol('not-an-occ')['valid'])
        otm=app.option_value_state('PUT',707,713.20,.75)
        self.assertEqual(otm['state'],'OTM')
        self.assertAlmostEqual(otm['distance_value'],6.2)
        self.assertEqual((otm['intrinsic'],otm['extrinsic']),(0.0,.75))
        itm=app.option_value_state('CALL',707,710.15,4.8)
        self.assertEqual(itm['state'],'ITM')
        self.assertAlmostEqual(itm['intrinsic'],3.15)
        self.assertAlmostEqual(itm['extrinsic'],1.65)

    def test_greeks_include_theta_and_vega(self):
        frozen=app.datetime(2026,8,19,12,0,tzinfo=app.NY)
        with mock.patch.object(app,'now_ny',return_value=frozen):
            greeks=app.greeks_snap(713,707,'2026-08-21',4.8,'CALL')
        self.assertIsNotNone(greeks['delta'])
        self.assertIsNotNone(greeks['gamma'])
        self.assertIsNotNone(greeks['theta'])
        self.assertIsNotNone(greeks['vega'])

    def test_canonical_endpoint_is_shared_for_open_and_closed_legacy_rows(self):
        self._wipe_trades()
        con=app.db()
        con.execute("""INSERT INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,status,trade_date,
                       expiry,entry_fill,exit_fill,pnl,exit_kind,origin)
                       VALUES(9001,'MVR','QQQ','PUT','QQQ260824P00707000',1,'CLOSED','2026-08-22',
                       '2026-08-24',.70,.92,22,'TARGET','SYSTEM')""")
        con.commit(); con.close()
        response=app.app.test_client().get('/api/trades/9001')
        self.assertEqual(response.status_code,200)
        item=response.get_json()
        self.assertEqual(item['identity']['label'],'QQQ · PUT ↓')
        self.assertEqual(item['identity']['strike'],707.0)
        self.assertEqual(item['availability']['contract_intelligence'],'NOT_CAPTURED')
        self.assertEqual(item['outcome']['realized_pnl'],22.0)

    def test_prediction_snapshots_append_without_rewriting_entry(self):
        con=app.db()
        con.execute("""INSERT OR IGNORE INTO trades(id,strategy_id,ticker,direction,option_symbol,qty,status,trade_date)
                       VALUES(9001,'MVR','QQQ','PUT','QQQ260824P00707000',1,'CLOSED','2026-08-22')""")
        con.execute('DELETE FROM trade_predictions WHERE trade_id=9001')
        con.commit(); con.close()
        entry={'kind':'ENTRY','ts':'2026-08-22T10:30:00-04:00','direction':'PUT',
               'horizon':'45-120 minutes','confidence':.68,'model':'test'}
        update={'kind':'UPDATE','ts':'2026-08-22T10:52:00-04:00','direction':'PUT',
                'horizon':'45-120 minutes','confidence':.75,'model':'test'}
        app.persist_prediction(9001,entry)
        app.persist_prediction(9001,update)
        con=app.db()
        rows=[dict(r) for r in con.execute(
            'SELECT kind,confidence FROM trade_predictions WHERE trade_id=9001 ORDER BY id').fetchall()]
        con.close()
        self.assertEqual(rows,[{'kind':'ENTRY','confidence':.68},{'kind':'UPDATE','confidence':.75}])

    def test_prediction_model_freezes_scenarios_premium_and_version_provenance(self):
        frozen=app.datetime(2026,8,22,10,30,tzinfo=app.NY)
        sig={'strategy_id':'MVR','ticker':'QQQ','direction':'PUT','score':1.25,
             'horizon':'EOD','details':{}}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            strategy=app._strategy_record('MVR')
            pred=app.prediction_snapshot(
                sig,strategy,spot=700,quote={'bid':.70,'ask':.74},greeks={'delta':-.48})
        self.assertEqual(strategy['version'],'1.0.0')
        self.assertNotEqual(strategy['version'],'unversioned')
        self.assertEqual(len(strategy['parameter_hash']),12)
        self.assertEqual(len(pred['scenarios']),4)
        self.assertIsNotNone(pred['target_premium_lo'])
        self.assertIsNotNone(pred['target_premium_hi'])
        self.assertIn('NOT_CALIBRATED',pred['payload']['confidence_provenance'])

    def test_execution_costs_distinguish_modeled_and_actual_slippage(self):
        costs=app.execution_costs({
            'qty':1,'entry_bid':1.0,'entry_ask':1.10,'entry_spread':.10,'entry_fill':1.08,
            'exit_bid':1.38,'exit_ask':1.42,'exit_spread':.04,'exit_fill':1.39,
        },entry_order={'commission':'0'},exit_order={'commission':'0'})
        self.assertEqual(costs['modeled_slippage'],7.0)
        self.assertEqual(costs['actual_slippage'],4.0)
        self.assertEqual(costs['fees'],0.0)

    def test_pnl_reconciliation_keeps_account_change_distinct(self):
        rows=[
            {'status':'CLOSED','trade_date':'2026-08-22','pnl':20,'fees':1,'slippage':2},
            {'status':'OPEN','trade_date':'2026-08-22','unrealized_pl':5,'fees':0,'slippage':0},
        ]
        got=app.pnl_reconciliation(rows,'2026-08-22',{'equity':10530,'last_equity':10000})
        self.assertEqual(got['session_total'],22.0)
        self.assertEqual(got['account_daily_change'],530.0)
        self.assertEqual(got['difference'],508.0)
        overnight=app.pnl_reconciliation(
            [{'status':'OPEN','trade_date':'2026-08-21','unrealized_pl':5,'fees':None,'slippage':None}],
            '2026-08-22',{'equity':10000,'last_equity':10015})
        self.assertEqual(overnight['unrealized'],5.0)
        self.assertFalse(overnight['cost_capture']['complete'])
        empty=app.pnl_reconciliation([],'2026-08-22',{'equity':10000,'last_equity':10000})
        self.assertFalse(empty['cost_capture']['complete'])

    def test_activity_is_a_tappable_ledger_with_one_inspector(self):
        response=app.app.test_client().get('/')
        html=response.get_data(as_text=True)
        response.close()
        self.assertIn('id="tradeInspector"',html)
        self.assertIn('function openTradeInspector(id,preserveReturn=false)',html)
        self.assertIn('class=activityTrade',html)
        self.assertIn('OPEN TRADE INSPECTOR',html)
        self.assertIn('Candidate set not captured for this legacy trade.',html)
        self.assertIn('TRADES ON THIS CHART',html)
        self.assertIn('function renderInspectTrades(rows)',html)
        self.assertIn('let svc=s.services||{}',html)
        self.assertIn('BROKER QUOTES',html)
        self.assertNotIn('id="closedThreads"',html)

    def test_unproven_context_stays_shadow_only(self):
        self._wipe_trades()
        con=app.db(); con.execute('DELETE FROM shadow_trades'); con.commit(); con.close()
        app.CFG.write_text(json.dumps({
            'broker_orders_enabled':True,'new_entries_enabled':True,
            'adaptive_allocator_enabled':True,
        }))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        sig={'strategy_id':'OPN','ticker':'TSLA','direction':'CALL','score':1.4}
        got=app.adaptive_entry_decision(sig,{'TSLA':{'regime':'TREND','ret':0.01,'rvol':1.5}})
        self.assertFalse(got['allow'])
        self.assertEqual(got['state'],'SHADOW')
        self.assertEqual(got['regime'],'TREND_UP')

    def test_active_override_cannot_bypass_missing_evidence(self):
        self._wipe_trades()
        con=app.db(); con.execute('DELETE FROM shadow_trades'); con.commit(); con.close()
        app.CFG.write_text(json.dumps({
            'broker_orders_enabled':True,'new_entries_enabled':True,
            'adaptive_allocator_enabled':True,
            'adaptive_strategy_states':{'OPN':'ACTIVE'},
        }))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        got=app.adaptive_entry_decision(
            {'strategy_id':'OPN','ticker':'TSLA','direction':'CALL','score':1},
            {'TSLA':{'regime':'TREND','ret':.01,'rvol':1.5}})
        self.assertFalse(got['allow'])
        self.assertEqual(got['state'],'SHADOW')

    def test_contextual_shadow_evidence_can_naturally_activate(self):
        self._wipe_trades()
        con=app.db(); con.execute('DELETE FROM shadow_trades')
        base=app.date_cls(2026,7,1)
        for i in range(30):
            day=(base+app.timedelta(days=i)).isoformat()
            con.execute("""INSERT INTO shadow_trades(
                           ts,trade_date,strategy_id,ticker,direction,status,entry_regime,
                           outcome_pnl,evaluated_at)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (day+'T10:00:00-04:00',day,'OPN','TSLA','CALL','SKIP_ADAPTIVE_SHADOW',
                         'TREND_UP',25,day+'T15:50:00-04:00'))
        con.commit(); con.close()
        app.CFG.write_text(json.dumps({
            'broker_orders_enabled':True,'new_entries_enabled':True,
            'adaptive_allocator_enabled':True,'adaptive_min_days':30,
            'adaptive_min_regime_days':10,
        }))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        frozen=app.datetime(2026,8,26,10,0,tzinfo=app.NY)
        with mock.patch.object(app,'now_ny',return_value=frozen):
            got=app.adaptive_entry_decision(
                {'strategy_id':'OPN','ticker':'TSLA','direction':'CALL','score':1},
                {'TSLA':{'regime':'TREND','ret':.01,'rvol':1.5}})
        self.assertTrue(got['allow'])
        self.assertEqual(got['state'],'ACTIVE')

    def test_paused_shadow_candidate_records_executable_outcome(self):
        self._wipe_trades()
        con=app.db(); con.execute('DELETE FROM shadow_trades'); con.commit(); con.close()
        entry_time=app.datetime(2026,8,26,9,51,tzinfo=app.NY)
        sig={'strategy_id':'OPN','ticker':'TSLA','direction':'CALL','horizon':'EOD','window':'09:51'}
        extra={
            'option':'TSLA260826C00350000','spot':350,'strike':350,'expiry':'2026-08-26',
            'horizon':'EOD','window':'09:51','qty':1,'regime':'TREND_UP',
            'quality':{'quote':{'bid':0.95,'ask':1.0}},'greeks':{'iv':0.5,'delta':0.5},
            'allocator':{'state':'SHADOW','version':app.ALLOCATOR_VERSION,'regime':'TREND_UP'},
            'skip_reason':'collecting evidence',
        }
        with mock.patch.object(app,'now_ny',return_value=entry_time):
            app.log_shadow(sig,'SKIP_ADAPTIVE_SHADOW',extra)
        exit_time=app.datetime(2026,8,26,15,51,tzinfo=app.NY)
        with mock.patch.object(app,'now_ny',return_value=exit_time), \
             mock.patch.object(app,'option_quote',return_value={'bid':1.5,'ask':1.55}):
            app.evaluate_shadow_outcomes()
            evidence=app.sleeve_evidence('OPN','TSLA','TREND_UP')
        con=app.db(); row=con.execute('SELECT outcome_pnl,evaluated_at FROM shadow_trades').fetchone(); con.close()
        self.assertEqual(row['outcome_pnl'],50.0)
        self.assertIsNotNone(row['evaluated_at'])
        self.assertEqual(evidence['context']['trades'],1)

    def test_weekly_high_water_pauses_new_risk(self):
        frozen=app.datetime(2026,8,26,10,0,tzinfo=app.NY)
        con=app.db(); con.execute('DELETE FROM account_snapshots')
        con.execute("""INSERT INTO account_snapshots(ts,equity) VALUES
                       ('2026-08-25T15:55:00-04:00',101000),
                       ('2026-08-26T09:30:00-04:00',100500)""")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen):
            reason,snap=app.account_equity_guard({'equity':100000})
        self.assertIn('weekly high-water giveback',reason)
        self.assertEqual(snap['weekly_high'],101000)

    def test_daily_equity_guard_uses_broker_previous_close(self):
        frozen=app.datetime(2026,8,26,10,0,tzinfo=app.NY)
        con=app.db(); con.execute('DELETE FROM account_snapshots')
        con.execute("INSERT INTO account_snapshots(ts,equity) VALUES('2026-08-26T09:55:00-04:00',99500)")
        con.commit(); con.close()
        with mock.patch.object(app,'now_ny',return_value=frozen):
            reason,snap=app.account_equity_guard({'equity':99400,'last_equity':100000})
        self.assertIn('daily equity loss limit',reason)
        self.assertEqual(snap['daily_start'],100000)

    def test_unconfirmed_entry_consumes_caps_and_unknown_debit_fails_closed(self):
        self._wipe_trades()
        con=app.db()
        con.execute("""INSERT INTO trades(strategy_id,ticker,direction,status,trade_date,signal_ts,qty)
                       VALUES('OPN','SPY','CALL','ENTRY_UNCONFIRMED','2026-08-26',
                              '2026-08-26T09:51:00-04:00',1)""")
        con.commit(); con.close()
        self.assertEqual(app.daily_fire_count('OPN','2026-08-26'),1)
        reason,_=app.portfolio_risk_block('IWM',1.0,1,{'equity':100000})
        self.assertIn('open debit unknown',reason)

    def test_portfolio_cap_blocks_third_concurrent_trade(self):
        self._wipe_trades()
        con=app.db()
        for ticker in ('SPY','QQQ'):
            con.execute("""INSERT INTO trades(strategy_id,ticker,direction,status,trade_date,qty,entry_fill)
                           VALUES('OPN',?,'CALL','OPEN','2026-08-26',1,1.0)""",(ticker,))
        con.commit(); con.close()
        reason,snap=app.portfolio_risk_block('IWM',1.0,1,{'equity':100000})
        self.assertIn('concurrent trade cap',reason)
        self.assertEqual(snap['open'],2)

    def test_grade_c_contract_fails_the_pretrade_checklist(self):
        self._wipe_trades()
        frozen=app.datetime(2026,8,19,9,51,tzinfo=app.NY)
        states={'IWM':{'c':302.22,'bars':22,'session_pct':0.95,'sym':'IWM'}}
        sig={'strategy_id':'OPN','ticker':'IWM','direction':'CALL','horizon':'EOD','window':'09:51'}
        quality={'score':60,'grade':'C','components':{},'quote':{}}
        with mock.patch.object(app,'now_ny',return_value=frozen), \
             mock.patch.object(app,'contract_quality',return_value=quality):
            status,extra=self._submit(sig,states)
        self.assertEqual(status,'SKIP_CHECKLIST')
        self.assertIn('grade C',extra['skip_reason'])

    def _submit(self, sig, states):
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        app.CFG.write_text(json.dumps({
            'alpaca_key':'k','alpaca_secret':'s','fred_key':'f','keys_ok':True,
            'broker_orders_enabled':True,'new_entries_enabled':True,
            'adaptive_allocator_enabled':False,'max_daily_fires':3,'max_cluster':5,
        }))
        spot=states[sig['ticker']]['c']
        opt=f"{sig['ticker']}260819C00001000"
        with mock.patch.object(app,'option_contract',return_value=(opt,'2026-08-19',spot,'0dte atm',{'dte':'0dte','moneyness':'atm'})), \
             mock.patch.object(app,'option_quote',return_value={'bid':1.0,'ask':1.05,'spread':0.05,'age_sec':1,'volume':1000}), \
             mock.patch.object(app,'pdt_block',return_value=None), \
             mock.patch.object(app,'account_equity_guard',return_value=(None,{'equity':100000})), \
             mock.patch.object(app,'portfolio_risk_block',return_value=(None,{'open':0})), \
             mock.patch.object(app,'session_coverage',return_value={sig['ticker']:{'pct':0.97}}), \
             mock.patch.object(app,'place_broker_order',return_value={'id':'ord-test'}), \
             mock.patch.object(app,'greeks_snap',return_value={'iv':0.2,'delta':0.5,'gamma':0.1}), \
             mock.patch.object(app,'log_contract'), \
             mock.patch.object(app,'log_shadow'), \
             mock.patch.object(app,'event'):
            return app.submit_entry(sig, states)

    def test_nlp_outage_blocks_news_sensitive_but_not_quantitative_signal(self):
        states={'SPY':{'news_nlp':{'status':'UNAVAILABLE'}}}
        quant={'strategy_id':'ORB','ticker':'SPY'}
        news={**quant,'strategy_id':'NEWS','requires_nlp':True}
        self.assertIsNone(app.nlp_required_block(quant,states))
        self.assertIn('unavailable',app.nlp_required_block(news,states))

    def test_fresh_confident_nlp_allows_news_sensitive_signal(self):
        frozen=app.datetime(2026,8,26,11,0,tzinfo=app.NY)
        states={'SPY':{'news_nlp':{
            'status':'READY','confidence':0.8,
            'source_ts':'2026-08-26T10:55:00-04:00',
        }}}
        app.CFG.write_text(json.dumps({'nlp_min_confidence':0.45,'nlp_max_age_sec':1800}))
        with mock.patch.object(app,'now_ny',return_value=frozen):
            self.assertIsNone(app.nlp_required_block(
                {'strategy_id':'NEWS','ticker':'SPY','requires_nlp':True},states))

    def test_explicit_exploration_lane_allows_one_lot_candidate(self):
        self._wipe_trades()
        app.CFG.write_text(json.dumps({
            'broker_orders_enabled':True,'new_entries_enabled':True,
            'adaptive_allocator_enabled':True,'adaptive_exploration_enabled':True,
        }))
        os.environ['CEG_ALLOW_BROKER_ORDERS']='true'
        got=app.adaptive_entry_decision(
            {'strategy_id':'N0D','ticker':'SPY','direction':'CALL','score':1},
            {'SPY':{'ret':.01,'rvol':1.3}})
        self.assertTrue(got['allow'])
        self.assertEqual(got['state'],'EXPLORE')

    def test_news_event_routes_to_one_evidence_horizon(self):
        frozen=app.datetime(2026,8,26,11,0,tzinfo=app.NY)
        states={'AAPL':{
            'rvol':1.1,
            'news_nlp':{
                'status':'READY','confidence':0.8,'novelty':0.9,'sentiment':0.6,
                'event_class':'EARNINGS','content_hash':'x'*64,
                'source_ts':'2026-08-26T10:55:00-04:00',
            },
        }}
        with mock.patch.object(app,'now_ny',return_value=frozen):
            signals,_=app.news_horizon_signals(states)
        self.assertEqual(len(signals),1)
        self.assertEqual(signals[0]['strategy_id'],'NWK')
        self.assertEqual(signals[0]['horizon'],'WEEKLY')
        self.assertTrue(signals[0]['requires_nlp'])

    def test_multi_horizon_exit_dates_use_market_sessions(self):
        self.assertEqual(app.horizon_exit_due('2026-04-02','OVERNIGHT'),'2026-04-06')
        self.assertEqual(app.horizon_exit_due('2026-04-02','WEEKLY'),'2026-04-10')
        self.assertGreater(app.horizon_exit_due('2026-04-02','MONTHLY'),'2026-04-20')

    def test_learning_status_never_returns_nlp_secret(self):
        app.CFG.write_text(json.dumps({
            'nlp_api_url':'http://100.64.0.2:8790',
            'nlp_shared_secret':'s'*40,
        }))
        response=app.app.test_client().get('/api/learning/status')
        self.assertEqual(response.status_code,200)
        payload=response.get_json()
        self.assertTrue(payload['nlp']['configured'])
        self.assertNotIn('secret',json.dumps(payload).lower())


if __name__=='__main__':
    unittest.main()
