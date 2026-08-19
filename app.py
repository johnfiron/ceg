from flask import Flask, request, jsonify, send_from_directory, send_file, Response, abort
from pathlib import Path
from datetime import datetime, timedelta, date as date_cls
from zoneinfo import ZoneInfo
import requests, sqlite3, json, os, time, math, statistics, threading, traceback, subprocess, shutil, zipfile, io, random, hashlib, hmac, re

ROOT=Path(__file__).resolve().parent
ENVIRONMENT=(os.environ.get('CEG_ENV') or 'development').strip().lower()
if ENVIRONMENT not in ('development','production','test'):
    raise RuntimeError('CEG_ENV must be development, production, or test')
STATIC=ROOT/'static'
DATA=Path(os.environ.get('CEG_DATA_DIR') or (ROOT/'data'/ENVIRONMENT)).expanduser()
DB=Path(os.environ.get('CEG_DB_PATH') or (DATA/'arena.db')).expanduser()
CFG=Path(os.environ.get('CEG_CONFIG_FILE') or (ROOT/f'config.{ENVIRONMENT}.json')).expanduser()
LIVE_DIR=DATA/'live'
DATA.mkdir(parents=True,exist_ok=True); LIVE_DIR.mkdir(parents=True,exist_ok=True)
def _seed_legacy_development_db():
    """First development boot should keep yesterday's Activity book, not an empty ledger."""
    if ENVIRONMENT!='development': return
    if os.environ.get('CEG_DB_PATH'): return
    legacy=ROOT/'data'/'arena.db'
    if DB.exists() or not legacy.exists(): return
    if legacy.resolve()==DB.resolve(): return
    shutil.copy2(legacy, DB)
_seed_legacy_development_db()
_SPLIT_LEDGER_LOGGED=False
def _log_split_development_ledger():
    """Do not merge. Say when yesterday's book is sitting next to the live development file."""
    global _SPLIT_LEDGER_LOGGED
    if _SPLIT_LEDGER_LOGGED or ENVIRONMENT!='development': return
    if os.environ.get('CEG_DB_PATH'): return
    legacy=ROOT/'data'/'arena.db'
    if not legacy.exists() or not DB.exists(): return
    if legacy.resolve()==DB.resolve(): return
    def _n(path):
        try:
            con=sqlite3.connect(path); n=con.execute('SELECT COUNT(*) FROM trades').fetchone()[0]; con.close(); return n
        except Exception:
            return None
    _SPLIT_LEDGER_LOGGED=True
    event(f'Development ledger {DB} ({_n(DB)} trades); unused legacy {legacy} ({_n(legacy)} trades)')
NY=ZoneInfo('America/New_York')
PAPER='https://paper-api.alpaca.markets/v2'
MD='https://data.alpaca.markets'
FRED='https://api.stlouisfed.org/fred'
TICKERS=['SPY','QQQ','IWM']
MIDDAY_TICKERS=['SPY','QQQ','IWM','AAPL','MSFT','NVDA','AMD','TSLA','META','AMZN']
ALL_TICKERS=list(dict.fromkeys(TICKERS+MIDDAY_TICKERS))
EOD_STRATEGY_IDS=['CEG','VCT','XED','LAR','RSI2','BB','MACD','DON','STO','KEL']
MIDDAY_STRATEGY_IDS=['OPN','OSF','ORB','VRC','MVR']
OPEN_TRADE_STATUSES=('ENTRY_SUBMITTED','OPEN','EXIT_SUBMITTED')
DESK_WINDOW_DAYS=30
_HIST_THREAD=None
NOTES=ROOT/'notes.md'
BACKUP_DIR=DATA/'backups'
app=Flask(__name__, static_folder=str(STATIC))

STRATEGIES=[
 {'id':'CEG','name':'Capitulation Exhaustion Gamma','origin':'Original novelty','author':'Original research session','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'RSI(3)<15 + close position<30% + 3:45 RVOL>1.2; VIX>=15 and macro-clear. Overnight 1% OTM weekly.','plain':'Crash-washout bounce held overnight. Needs VIX≥15, real volume, and a washed-out close. Quiet VIX days (like 14.25) are a pass.'},
 {'id':'VCT','name':'Volume-Confirmed Tail','origin':'Original novelty','author':'Original research session','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'Large lower shadow + positive candle + 3:45 RVOL>1.2.','plain':'Sellers pushed a tail and lost. Needs a long lower wick, a green close, and volume.'},
 {'id':'XED','name':'Cross-Index Exhaustion Divergence','origin':'New novelty','author':'V5.3 hypothesis','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'Laggard index shows exhaustion while the other indices materially outperform intraday.','plain':'One index is dumped while the others hold up. Buy the laggard’s exhaustion, not a broad selloff.'},
 {'id':'LAR','name':'Late-Day Absorption Reversal','origin':'New novelty','author':'V5.3 hypothesis','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'New 5-day low followed by strong 3:00-3:45 recovery, high close position and elevated volume.','plain':'Made a new 5-day low then recovered into the close. The low was absorbed, not a breakdown.'},
 {'id':'RSI2','name':'RSI(2) Pullback','origin':'Established','author':'Connors-style','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'Uptrend above SMA200 with RSI(2)<10.','plain':'Still in a bigger uptrend (above the 200-day) but 2-day RSI is washed out. Overnight bounce bet. Fired today on SPY/QQQ but was blocked by a false thin-tape gate.'},
 {'id':'BB','name':'Bollinger Mean Reversion','origin':'Established','author':'Bollinger-style','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'Close outside 20-day, 2σ band; trade back toward mean.','plain':'Close outside the 20-day, 2σ band. Fade back toward the middle, not a breakout.'},
 {'id':'MACD','name':'MACD Crossover','origin':'Established','author':'Appel-style','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'12/26 MACD crossing its 9-period signal line.','plain':'Daily MACD just crossed its signal line. Trend-turn, not a fade.'},
 {'id':'DON','name':'Donchian Breakout','origin':'Established','author':'Donchian-style','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'Break above/below prior 20-session price channel.','plain':'New 20-day high or low. Continuation breakout, held overnight.'},
 {'id':'STO','name':'Stochastic Reversal','origin':'Established','author':'Lane-style','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'14-period stochastic crossing from oversold/overbought territory.','plain':'14-day stochastic turning up from oversold or down from overbought. Fired PUTs today on QQQ/IWM — opposite RSI2’s CALLs on QQQ.'},
 {'id':'KEL','name':'Keltner Breakout','origin':'Established','author':'Keltner-style','session':'15:45','horizon':'OVERNIGHT','opt':{'dte':'next','moneyness':'otm1'},'desc':'Close beyond EMA20 ± 2×ATR20.','plain':'Late-day trend continuation. Only if the close is clearly outside the Keltner channel.'},
 {'id':'OPN','name':'Opening Swing','origin':'New open','author':'Gap-and-go / opening drive','session':'09:35-09:55','horizon':'EOD','opt':{'dte':'0dte','moneyness':'atm'},'desc':'Trade a gap that is still holding in the first 20 minutes. ATM same-day option so the opening drive can show in P&L.','plain':'If the index gaps ≥0.35% and has not given the gap back by 09:35–09:55, ride that opening swing to the close. CALL on a held gap-up, PUT on a held gap-down. Invalidation: price back through yesterday’s close.'},
 {'id':'OSF','name':'Opening Swing Failure','origin':'New open','author':'Failed drive fade','session':'09:50-10:25','horizon':'EOD','opt':{'dte':'0dte','moneyness':'atm'},'desc':'Fade a gap/drive that has already reversed through the prior close. ATM 0DTE.','plain':'The open tried to swing and failed. If a ≥0.35% gap has already crossed back through yesterday’s close, fade it (PUT after a failed gap-up, CALL after a failed gap-down). This is the opposite of OPN.'},
 {'id':'ORB','name':'Opening Range Breakout','origin':'New midday','author':'Intraday session','session':'10:05-11:30','horizon':'EOD','opt':{'dte':'0dte','moneyness':'atm'},'desc':'First break of the 09:30-10:00 range with time-adjusted RVOL; ATM same-day option so the break can show in P&L.','plain':'After 10:00 the 30-minute range is locked. First genuine break with volume, not a name that was already outside at 10:05.'},
 {'id':'VRC','name':'VWAP Reclaim','origin':'New midday','author':'Trend continuation','session':'10:30-13:00','horizon':'EOD','opt':{'dte':'0dte','moneyness':'atm'},'desc':'Ride a reclaim of session VWAP rather than fading a stretch. ATM 0DTE.','plain':'Opposite of MVR. If price spent time on one side of VWAP and then reclaims it with volume, go with the reclaim (CALL reclaim from below, PUT lose VWAP from above).'},
 {'id':'MVR','name':'Midday VWAP Reversion','origin':'New midday','author':'Intraday session','session':'11:00-14:30','horizon':'EOD','opt':{'dte':'0dte','moneyness':'atm'},'desc':'Fade a 5-min RSI extreme stretched from session VWAP; ATM same-day option so a VWAP snapback can show in P&L.','plain':'Mean-reversion sleeve. Only when stretched ≥1.25 ATR from VWAP and 5-min RSI is extreme. Today’s 2¢ 0DTEs did not express this; ATM is the point of the style.'},
]

def now_ny(): return datetime.now(NY)

def paper_api_url(path):
    """Return an Alpaca paper URL and fail closed if the broker origin ever changes."""
    if PAPER != 'https://paper-api.alpaca.markets/v2':
        raise RuntimeError('refusing non-paper Alpaca broker endpoint')
    if not isinstance(path,str) or not path.startswith('/') or '://' in path:
        raise RuntimeError('invalid Alpaca paper API path')
    return PAPER+path

def session_clock(n=None):
    """What the runner is doing now, and when the next decision window starts."""
    n=n or now_ny(); hm=n.strftime('%H:%M'); wd=n.weekday()
    windows=[
        {'id':'OPN','label':'Opening swing (gap-and-go)','start':'09:35','end':'09:55'},
        {'id':'OSF','label':'Opening swing failure','start':'09:50','end':'10:25'},
        {'id':'ORB','label':'Opening-range breakout','start':'10:05','end':'11:30'},
        {'id':'VRC','label':'VWAP reclaim','start':'10:30','end':'13:00'},
        {'id':'MVR','label':'VWAP reversion fade','start':'11:00','end':'14:30'},
        {'id':'EOD','label':'3:45 overnight models','start':'15:45','end':'15:49'},
        {'id':'EXIT','label':'Same-day exits','start':'15:50','end':'16:05'},
    ]
    if wd>=5:
        return {'hm':hm,'phase':'WEEKEND','label':'Weekend — no scan','current':[],'next':None,'remaining':None}
    current=[w for w in windows if w['start']<=hm<=w['end']]
    upcoming=[w for w in windows if hm<w['start']]
    nxt=upcoming[0] if upcoming else None
    def mins_until(hhmm):
        t=datetime.strptime(hhmm,'%H:%M')
        nowt=datetime.strptime(hm,'%H:%M')
        return int((t-nowt).total_seconds()//60)
    if hm>'16:10':
        phase,label,remain='CLOSED','Session closed',None
    elif current:
        phase=current[0]['id']
        label=' · '.join(w['label'] for w in current)
        remain=mins_until(min(w['end'] for w in current))
    elif hm<'09:25':
        phase,label,remain='PRE','Tape starts 09:25',mins_until('09:25')
    else:
        phase,label='WATCH','Between windows'
        remain=mins_until(nxt['start']) if nxt else None
    return {'hm':hm,'phase':phase,'label':label,'current':[w['id'] for w in current],
            'next':({'id':nxt['id'],'label':nxt['label'],'start':nxt['start']} if nxt else None),
            'remaining':remain}

def _clip01(x):
    try:
        v=float(x)
        if v!=v: return 0.0
        return max(0.0, min(1.0, v))
    except Exception:
        return 0.0

def setup_proximity(s, hm=None):
    """AND-gate progress toward a live fire. Bottleneck is the weakest gate on the best CALL/PUT path."""
    hm=hm or now_ny().strftime('%H:%M')
    cands=[]
    rv=s.get('rvol') or 0; c=s.get('c')
    gap=s.get('gap_pct'); pc=s.get('prev_close')
    if '09:35'<=hm<='09:55':
        g_rvol=_clip01(rv/1.0); g_gap=0.0; side=None
        if gap is not None:
            g_gap=_clip01(abs(gap)/0.0035)
            if gap>=0.0035 and c and pc and c>=pc: side='CALL'; g_hold=1.0 if c>=pc else 0.2
            elif gap<=-0.0035 and c and pc and c<=pc: side='PUT'; g_hold=1.0 if c<=pc else 0.2
            else: g_hold=_clip01(abs(gap)/0.0035)*0.4
        else: g_hold=0.0
        gates={'rvol':round(g_rvol,3),'gap':round(g_gap,3),'hold':round(g_hold,3)}
        score=min(gates.values()) if gates else 0
        fired=bool(rv>=1.0 and gap is not None and abs(gap)>=0.0035 and c and pc and ((gap>0 and c>=pc) or (gap<0 and c<=pc)))
        cands.append({'window':'OPN','score':round(score,3),'side':side,
                      'bottleneck':'FIRED' if fired else min(gates,key=gates.get),
                      'gates':gates,'fired':fired})
    if '09:50'<=hm<='10:25':
        g_rvol=_clip01(rv/0.8); g_fail=0.0; side=None
        if gap is not None and c and pc:
            if gap>=0.0035 and c<pc: g_fail=1.0; side='PUT'
            elif gap<=-0.0035 and c>pc: g_fail=1.0; side='CALL'
            else: g_fail=_clip01(abs(gap)/0.0035)*0.3
        gates={'rvol':round(g_rvol,3),'fail':round(g_fail,3)}
        score=min(gates.values()) if gates else 0
        fired=bool(rv>=0.8 and g_fail>=0.999)
        cands.append({'window':'OSF','score':round(score,3),'side':side,
                      'bottleneck':'FIRED' if fired else min(gates,key=gates.get),
                      'gates':gates,'fired':fired})
    if '10:05'<=hm<='11:30':
        orh,orl=s.get('or_high'),s.get('or_low')
        g_rvol=_clip01(rv/1.0); g_or=0.0; side=None
        if orh and orl and c and orh>orl:
            mid=(orh+orl)/2
            if c>=orh: g_or=1.0; side='CALL'
            elif c<=orl: g_or=1.0; side='PUT'
            else:
                g_or=_clip01(abs(c-mid)/((orh-orl)/2))
                side='CALL' if c>=mid else 'PUT'
        gates={'rvol':round(g_rvol,3),'range':round(g_or,3)}
        score=min(gates.values()) if gates else 0
        cands.append({'window':'ORB','score':round(score,3),'side':side,
                      'bottleneck':'FIRED' if score>=0.999 else min(gates,key=gates.get),
                      'gates':gates,'fired':score>=0.999})
    if '10:30'<=hm<='13:00':
        rec=s.get('reclaim'); dist=s.get('vwap_dist_atr')
        g_rvol=_clip01(rv/0.9)
        g_rec=1.0 if rec in ('UP','DOWN') else 0.2
        side='CALL' if rec=='UP' else ('PUT' if rec=='DOWN' else None)
        gates={'rvol':round(g_rvol,3),'reclaim':round(g_rec,3)}
        if dist is not None: gates['through']=round(_clip01(abs(dist)/0.2),3)
        score=min(gates.values()) if gates else 0
        fired=bool(rv>=0.9 and rec in ('UP','DOWN') and dist is not None and abs(dist)>=0.2)
        cands.append({'window':'VRC','score':round(score,3),'side':side,
                      'bottleneck':'FIRED' if fired else min(gates,key=gates.get),
                      'gates':gates,'fired':fired})
    if '11:00'<=hm<='14:30':
        dist=s.get('vwap_dist_atr'); rsi=s.get('rsi5')
        g_rvol=_clip01(rv/0.8)
        if dist is None or rsi is None:
            cands.append({'window':'MVR','score':round(g_rvol*0.25,3),'side':None,'bottleneck':'need VWAP/RSI',
                          'gates':{'rvol':round(g_rvol,3)},'fired':False})
        else:
            g_call_s=_clip01((-dist)/1.25); g_call_r=_clip01((50-rsi)/18)
            g_put_s=_clip01(dist/1.25); g_put_r=_clip01((rsi-50)/18)
            call=min(g_rvol,g_call_s,g_call_r); put=min(g_rvol,g_put_s,g_put_r)
            if call>=put:
                gates={'rvol':round(g_rvol,3),'stretch':round(g_call_s,3),'rsi':round(g_call_r,3)}; side='CALL'; score=call
            else:
                gates={'rvol':round(g_rvol,3),'stretch':round(g_put_s,3),'rsi':round(g_put_r,3)}; side='PUT'; score=put
            fired=bool(rv>=0.8 and ((dist<=-1.25 and rsi<=32) or (dist>=1.25 and rsi>=68)))
            cands.append({'window':'MVR','score':round(score,3),'side':side,
                          'bottleneck':'FIRED' if fired else min(gates,key=gates.get),
                          'gates':gates,'fired':fired})
    if not cands:
        best={'window':'WATCH','score':0,'side':None,'bottleneck':'outside scan window','gates':{},'fired':False}
    else:
        best=max(cands, key=lambda x:x.get('score') or 0)
    bn=best.get('bottleneck')
    best['bottleneck_en']=BOTTLENECK_EN.get(bn, bn)
    return best

BOTTLENECK_EN={
    'rvol':'waiting on volume (RVOL still light)',
    'gap':'gap is smaller than 0.35%',
    'hold':'the opening gap is already being given back',
    'fail':'the gap has not failed through yesterday’s close yet',
    'range':'still inside the 09:30–10:00 opening range',
    'reclaim':'has not reclaimed VWAP yet',
    'through':'reclaim is only a tag, not through VWAP',
    'stretch':'not stretched far enough from VWAP',
    'rsi':'RSI is not extreme with the stretch',
    'need VWAP/RSI':'need VWAP and 5-minute RSI',
    'outside scan window':'no strategy is scanning right now',
    'FIRED':'this setup is at the fire line',
}

def explain_now(live=None, rm=None, ws=None):
    """Plain-language status for the dashboard. Not a trade recommendation."""
    clk=session_clock(); hm=clk.get('hm') or now_ny().strftime('%H:%M')
    live=live or {}
    rm=rm or {}
    ws=ws or {}
    today=(rm.get('today') or {})
    paras=[]; why=[]
    phase=clk.get('phase')
    if phase=='WEEKEND':
        headline='Weekend. No scans.'
        paras.append('The runner sleeps until Monday 09:25. Use Lab to review fire rates — sample is unique days, not same-day fills.')
    elif phase=='CLOSED' or hm>'16:10':
        headline='Session closed.'
        paras.append('Scanning is done. Same-day 0DTE that were still open were expired at the close (premium → 0). Overnight entries, if any, exit after 09:35 tomorrow.')
        if today.get('fires'):
            paras.append(f"Today the journal recorded {today.get('fires') or 0} fires and {today.get('misses') or 0} misses across {today.get('opportunities') or 0} opportunities. Top miss: {today.get('top_miss') or '—'}.")
        paras.append('Tomorrow the new opening-swing window starts at 09:35 (OPN), then OSF 09:50, ORB 10:05, VWAP reclaim 10:30, MVR fade 11:00, and the 15:45 overnight book.')
    elif phase=='PRE':
        headline=f"Tape starts in {clk.get('remaining')} minutes."
        paras.append('Runner will ingest from 09:25. First decision window is OPN (opening swing) at 09:35: a gap that is still holding.')
    else:
        cur=clk.get('current') or []
        if cur:
            headline=clk.get('label') or 'Scanning'
            paras.append(f"{hm} ET — live window: {clk.get('label')}. {clk.get('remaining')} minutes left in the nearest end.")
        else:
            nxt=clk.get('next') or {}
            headline=f"Between windows. Next: {nxt.get('id') or '—'} at {nxt.get('start') or '—'}"
            paras.append(f"{hm} ET — {clk.get('label')}. The runner is still ingesting the tape so the next window has a full session, not a snapshot.")
        watch=(live.get('watchlist') or [])[:3]
        for w in watch:
            st=w.get('setup') or {}
            bn=st.get('bottleneck') or '—'
            en=BOTTLENECK_EN.get(bn, bn)
            why.append(f"{w.get('sym')}: {st.get('window') or ''} {st.get('side') or ''} — {en} ({int((st.get('score') or 0)*100)}% to fire).")
        if why:
            paras.append('Closest names: ' + ' '.join(why[:2]))
    vix=ws.get('vix')
    if vix is not None:
        paras.append(f"VIX {float(vix):.1f} — CEG wants ≥15, so capitulation is {'allowed' if float(vix)>=15 else 'blocked'} on that gate.")
    if ws.get('macro_clear') is False:
        paras.append('Macro calendar is blocking overnight entries (tomorrow is a mapped event).')
    dnt=ws.get('dnt') or live.get('dnt') or {}
    if dnt:
        bits=[f"{k} ({', '.join(v)})" for k,v in list(dnt.items())[:4]]
        paras.append('Do-not-trade right now: ' + '; '.join(bits) + '.')
    play=[]
    for p in (ws.get('playbook') or []):
        play.append(f"{p.get('strategy_id')} {p.get('ticker')} ×{p.get('qty')} — {'sell now' if p.get('ready') else 'queued exit '+str(p.get('exit_at'))}.")
    if not play:
        play.append('No open exits queued.')
    books=[
        {'id':'OPN','when':'09:35–09:55','what':'Opening swing: held gap-and-go. ATM 0DTE to the close.'},
        {'id':'OSF','when':'09:50–10:25','what':'Failed opening swing: fade a gap that already crossed yesterday’s close.'},
        {'id':'ORB','when':'10:05–11:30','what':'First break of the locked 09:30–10:00 range.'},
        {'id':'VRC','when':'10:30–13:00','what':'VWAP reclaim (trend). Opposite of the MVR fade.'},
        {'id':'MVR','when':'11:00–14:30','what':'VWAP stretch fade with extreme 5-min RSI. ATM, not a 2¢ lottery.'},
        {'id':'EOD','when':'15:45','what':'Ten overnight models on SPY/QQQ/IWM. Next-week 1% OTM. Exit after 09:35 tomorrow.'},
    ]
    return {'headline':headline,'paragraphs':paras,'why_not':why,'playbook':play,'books':books,'clock':clk}

def normalize_reason(reason):
    r=(reason or 'NO SIGNAL').strip(); low=r.lower()
    if low.startswith('rvol') and '<' in r: return 'rvol below threshold'
    if 'not stretched' in low: return 'not stretched vs VWAP'
    if 'not extreme' in low: return 'RSI not extreme with stretch'
    if 'inside opening range' in low: return 'inside opening range'
    if 'opening range incomplete' in low: return 'opening range incomplete'
    if 'need vwap' in low: return 'need VWAP + 5m ATR/RSI'
    if 'too early' in low: return 'too early in the open'
    if 'need prior close' in low: return 'need prior close for gap'
    if 'too small to fade' in low: return 'gap too small to fade'
    if 'given back' in low: return 'gap already given back'
    if 'still holding' in low: return 'gap still holding'
    if 'no vwap reclaim' in low: return 'no VWAP reclaim yet'
    if 'atr through' in low: return 'reclaim only a tag'
    if 'gap' in low and '<' in r: return 'gap below threshold'
    return r

def cfg():
    if CFG.exists():
        try:return json.loads(CFG.read_text())
        except:pass
    return {}

def broker_runtime_armed():
    """Second, process-level interlock. A config/UI change alone cannot arm orders."""
    return (os.environ.get('CEG_ALLOW_BROKER_ORDERS') or '').strip().lower() in ('1','true','yes')

def broker_orders_enabled():
    """Fail closed unless both the config and runtime interlocks are explicitly armed."""
    return cfg().get('broker_orders_enabled') is True and broker_runtime_armed()

def keys_ok():
    c=cfg()
    return bool(c.get('alpaca_key') and c.get('alpaca_secret') and c.get('fred_key') and c.get('keys_ok'))

def save_cfg(c):
    CFG.write_text(json.dumps(c,indent=2))
    try: os.chmod(CFG,0o600)
    except: pass

def thresh(book=None):
    c=cfg(); d=dict(c.get('thresholds') or {})
    if book=='B':
        d.update(c.get('thresholds_b') or {})
    return {
        'mvr_rvol':float(d.get('mvr_rvol',0.8)),
        'mvr_stretch':float(d.get('mvr_stretch',1.25)),
        'mvr_rsi_lo':float(d.get('mvr_rsi_lo',32)),
        'mvr_rsi_hi':float(d.get('mvr_rsi_hi',68)),
        'orb_rvol':float(d.get('orb_rvol',1.0)),
        'max_daily_fires':int(c.get('max_daily_fires',3)),
        'max_cluster':int(c.get('max_cluster',3)),
        'time_stop_min':int(c.get('time_stop_min',90)),
        'min_und_move':float(c.get('min_und_move',0.0015)),
        'scale_mfe':float(c.get('scale_mfe',0.004)),
        'bp_frac':float(c.get('bp_frac',0.08)),
        'quote_max_age_sec':float(c.get('quote_max_age_sec',15)),
        'clock_skew_sec':float(c.get('clock_skew_sec',8)),
        'opn_gap':float(d.get('opn_gap',0.0035)),
        'opn_rvol':float(d.get('opn_rvol',1.0)),
        'osf_gap':float(d.get('osf_gap',0.0035)),
        'vrc_atr':float(d.get('vrc_atr',0.2)),
        'vrc_rvol':float(d.get('vrc_rvol',0.9)),
    }

def ab_book(ticker):
    c=cfg()
    if not (c.get('thresholds_b') or {}):
        return 'A', thresh('A')
    h=sum(ord(x) for x in str(ticker)) % 2
    book='B' if h else 'A'
    return book, thresh(book)

def _ncdf(x):
    return 0.5*(1.0+math.erf(float(x)/math.sqrt(2.0)))

def _npdf(x):
    return math.exp(-0.5*float(x)*float(x))/math.sqrt(2.0*math.pi)

def bs_price(S,K,T,sig,call=True,r=0.045):
    if T is None or T<=0 or sig is None or sig<=0 or S<=0 or K<=0:
        return max(S-K,0.0) if call else max(K-S,0.0)
    d1=(math.log(S/K)+(r+0.5*sig*sig)*T)/(sig*math.sqrt(T))
    d2=d1-sig*math.sqrt(T)
    if call: return S*_ncdf(d1)-K*math.exp(-r*T)*_ncdf(d2)
    return K*math.exp(-r*T)*_ncdf(-d2)-S*_ncdf(-d1)

def implied_vol(S,K,T,price,call=True,r=0.045):
    if not S or not K or T is None or T<=0 or not price or price<=0: return None
    lo,hi=0.01,5.0
    for _ in range(48):
        mid=(lo+hi)/2.0
        p=bs_price(S,K,T,mid,call,r)
        if p>price: hi=mid
        else: lo=mid
    return round((lo+hi)/2.0,4)

def greeks_snap(S,K,expiry,mid,direction):
    try:
        exp=datetime.strptime(str(expiry)[:10],'%Y-%m-%d').replace(hour=16,minute=0,tzinfo=NY)
        T=max((exp-now_ny()).total_seconds(), 30*60)/(365.0*24*3600)
    except Exception:
        T=1/365.0
    call=str(direction).upper()!='PUT'
    iv=implied_vol(float(S),float(K),T,float(mid or 0),call)
    if not iv:
        return {'iv':None,'delta':None,'gamma':None,'t_years':round(T,6)}
    d1=(math.log(float(S)/float(K))+(0.045+0.5*iv*iv)*T)/(iv*math.sqrt(T))
    delta=_ncdf(d1) if call else _ncdf(d1)-1
    gamma=_npdf(d1)/(float(S)*iv*math.sqrt(T))
    return {'iv':iv,'delta':round(delta,4),'gamma':round(gamma,6),'t_years':round(T,6)}

def parse_ny(ts):
    if not ts:return None
    try:
        dt=datetime.fromisoformat(str(ts).replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=ZoneInfo('UTC'))
        return dt.astimezone(NY)
    except Exception: return None

def realized_date(trade):
    """New York session date on which a closed trade actually realized P/L."""
    dt=parse_ny((trade or {}).get('exit_filled_at'))
    if dt:return dt.date().isoformat()
    return str((trade or {}).get('trade_date') or '')[:10]

def realized_sort_key(trade):
    dt=parse_ny((trade or {}).get('exit_filled_at'))
    if dt:stamp=dt.timestamp()
    else:
        try:
            stamp=datetime.strptime(realized_date(trade),'%Y-%m-%d').replace(tzinfo=NY).timestamp()
        except Exception:stamp=0
    return stamp,int((trade or {}).get('id') or 0)

def years_to_expiry(expiry):
    try:
        exp=datetime.strptime(str(expiry)[:10],'%Y-%m-%d').replace(hour=16,minute=0,tzinfo=NY)
        return max((exp-now_ny()).total_seconds(), 30*60)/(365.0*24*3600)
    except Exception:
        return 1/365.0

def ah():
    c=cfg(); return {'APCA-API-KEY-ID':c.get('alpaca_key',''),'APCA-API-SECRET-KEY':c.get('alpaca_secret','')}

_MEM_CACHE={}
_API_STATS={'hits':0,'misses':0,'calls':0}

def _short_path(url):
    return url.replace('https://paper-api.alpaca.markets','').replace('https://data.alpaca.markets','').replace('https://api.stlouisfed.org','')[:180]

def _log_api(method,url,status,ms,note=''):
    _API_STATS['calls']+=1
    try:
        con=db(); con.execute('INSERT INTO api_log(ts,method,path,status,ms,note) VALUES(?,?,?,?,?,?)',
                              (now_ny().isoformat(),method,_short_path(url),str(status),int(ms),note[:120]))
        con.execute("DELETE FROM api_log WHERE id NOT IN (SELECT id FROM api_log ORDER BY id DESC LIMIT 2500)")
        con.commit(); con.close()
    except Exception: pass

def getj(url,headers=None,params=None,timeout=30):
    t0=time.time()
    r=requests.get(url,headers=headers or {},params=params or {},timeout=timeout)
    _log_api('GET',url,r.status_code,(time.time()-t0)*1000)
    if not r.ok: raise RuntimeError(f'{r.status_code} {r.reason}: {r.text[:260]}')
    return r.json()

def cache_get(key,ttl):
    now=time.time(); hit=_MEM_CACHE.get(key)
    if hit and now-hit[0]<ttl:
        _API_STATS['hits']+=1; return hit[1]
    try:
        con=db(); r=con.execute('SELECT ts,payload FROM api_cache WHERE k=?',(key,)).fetchone(); con.close()
        if r:
            age=(now_ny()-datetime.fromisoformat(r['ts'])).total_seconds()
            if age<ttl:
                payload=json.loads(r['payload']); _MEM_CACHE[key]=(now,payload); _API_STATS['hits']+=1; return payload
    except Exception: pass
    _API_STATS['misses']+=1; return None

def cache_set(key,payload,ttl=None):
    _MEM_CACHE[key]=(time.time(),payload)
    try:
        con=db(); con.execute('INSERT INTO api_cache(k,ts,payload) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET ts=excluded.ts,payload=excluded.payload',
                              (key,now_ny().isoformat(),json.dumps(payload,default=str))); con.commit(); con.close()
    except Exception: pass

def getj_cached(url,headers=None,params=None,timeout=30,ttl=20,key=None):
    k=key or (url+'|'+json.dumps(params or {},sort_keys=True,default=str))
    hit=cache_get(k,ttl)
    if hit is not None: return hit
    j=getj(url,headers,params,timeout); cache_set(k,j); return j

def postj(url,payload,timeout=8):
    r=requests.post(url,headers={**ah(),'Content-Type':'application/json'},json=payload,timeout=timeout)
    if not r.ok: raise RuntimeError(f'{r.status_code} {r.reason}: {r.text[:300]}')
    return r.json()

def broker_order_by_client_id(client_id):
    if not client_id:return None
    try:
        return getj(paper_api_url('/orders:by_client_order_id'),ah(),{'client_order_id':client_id},timeout=8)
    except Exception:
        return None

def place_broker_order(payload):
    """Submit an Alpaca paper order once, recovering the same client id after a crash."""
    if not broker_orders_enabled():
        raise RuntimeError('broker orders are disabled')
    client_id=(payload or {}).get('client_order_id')
    if not client_id:
        raise RuntimeError('broker order requires a client_order_id')
    existing=broker_order_by_client_id(client_id)
    if existing:return existing
    try:
        return postj(paper_api_url('/orders'),payload)
    except Exception:
        # The request can succeed at Alpaca while the response is lost locally.
        # Re-querying the deterministic id closes that crash window.
        existing=broker_order_by_client_id(client_id)
        if existing:return existing
        raise

def mem_get(key,ttl):
    hit=_MEM_CACHE.get(key)
    if hit and time.time()-hit[0]<ttl:
        return hit[1]
    return None

def mem_set(key,payload):
    _MEM_CACHE[key]=(time.time(),payload)

def db():
    con=sqlite3.connect(DB,timeout=30,check_same_thread=False)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=8000')
    con.execute('PRAGMA synchronous=NORMAL')
    return con

def init_db():
    con=db(); con.executescript('''
    CREATE TABLE IF NOT EXISTS signals(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, strategy_id TEXT, ticker TEXT, direction TEXT, score REAL, details TEXT, execution_status TEXT, note TEXT);
    CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT, strategy_id TEXT, ticker TEXT, direction TEXT, option_symbol TEXT, qty INTEGER, signal_ts TEXT, trade_date TEXT, expiry TEXT, entry_order_id TEXT, entry_client_id TEXT, entry_fill REAL, entry_filled_at TEXT, exit_due_date TEXT, exit_order_id TEXT, exit_client_id TEXT, exit_fill REAL, exit_filled_at TEXT, status TEXT, pnl REAL, broker_note TEXT);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, level TEXT, message TEXT);
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT);
    CREATE TABLE IF NOT EXISTS snapshots(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, ticker TEXT,
      freeze_time TEXT, feed TEXT, payload TEXT, UNIQUE(trade_date,ticker,freeze_time,feed)
    );
    CREATE TABLE IF NOT EXISTS strategy_journal(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, strategy_id TEXT,
      ticker TEXT, eligible INTEGER, direction TEXT, score REAL, reason TEXT, metrics TEXT,
      UNIQUE(trade_date,strategy_id,ticker)
    );
    CREATE TABLE IF NOT EXISTS live_bars(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ingested_at TEXT, trade_date TEXT, ticker TEXT, timeframe TEXT,
      t TEXT, o REAL, h REAL, l REAL, c REAL, v REAL, vw REAL, n INTEGER,
      UNIQUE(ticker, timeframe, t)
    );
    CREATE TABLE IF NOT EXISTS live_quotes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, ticker TEXT,
      bid REAL, ask REAL, last REAL, bid_sz REAL, ask_sz REAL, payload TEXT
    );
    CREATE TABLE IF NOT EXISTS midday_evals(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, strategy_id TEXT,
      ticker TEXT, window TEXT, eligible INTEGER, direction TEXT, score REAL, reason TEXT, metrics TEXT,
      UNIQUE(trade_date,strategy_id,ticker,window)
    );
    CREATE TABLE IF NOT EXISTS api_cache(
      k TEXT PRIMARY KEY, ts TEXT, payload TEXT
    );
    CREATE TABLE IF NOT EXISTS api_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, method TEXT, path TEXT, status TEXT, ms INTEGER, note TEXT
    );
    CREATE TABLE IF NOT EXISTS contract_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, strategy_id TEXT, ticker TEXT,
      direction TEXT, spot REAL, strike REAL, expiry TEXT, option_symbol TEXT, dte TEXT, moneyness TEXT, reason TEXT
    );
    CREATE TABLE IF NOT EXISTS live_bar_holes(
      ticker TEXT, trade_date TEXT, hm TEXT, probed_at TEXT,
      PRIMARY KEY(ticker, trade_date, hm)
    );
    CREATE INDEX IF NOT EXISTS idx_live_bars_lookup ON live_bars(trade_date, ticker, timeframe, t);
    CREATE INDEX IF NOT EXISTS idx_live_quotes_lookup ON live_quotes(trade_date, ticker, ts);
    ''')
    def addcol(table,col,spec):
        names={r[1] for r in con.execute(f'PRAGMA table_info({table})')}
        if col not in names: con.execute(f'ALTER TABLE {table} ADD COLUMN {col} {spec}')
    addcol('signals','window','TEXT')
    addcol('signals','horizon','TEXT')
    addcol('trades','horizon','TEXT')
    addcol('trades','window','TEXT')
    addcol('trades','entry_bid','REAL')
    addcol('trades','entry_ask','REAL')
    addcol('trades','entry_spread','REAL')
    addcol('trades','contract_score','REAL')
    addcol('trades','checklist','TEXT')
    addcol('trades','cluster_n','INTEGER')
    addcol('trades','atm_spot','REAL')
    addcol('trades','comment','TEXT')
    addcol('trades','skip_reason','TEXT')
    addcol('trades','entry_iv','REAL')
    addcol('trades','entry_delta','REAL')
    addcol('trades','entry_gamma','REAL')
    addcol('trades','mae','REAL')
    addcol('trades','mfe','REAL')
    addcol('trades','exit_kind','TEXT')
    addcol('trades','scaled_qty','INTEGER')
    addcol('trades','ab_book','TEXT')
    addcol('trades','greeks','TEXT')
    addcol('events','seen','INTEGER')
    addcol('events','code','TEXT')
    con.execute('''CREATE TABLE IF NOT EXISTS lab_snapshots(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, label TEXT, payload TEXT)''')
    con.execute('''CREATE TABLE IF NOT EXISTS shadow_trades(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, strategy_id TEXT, ticker TEXT,
      direction TEXT, option_symbol TEXT, status TEXT, skip_reason TEXT, spot REAL, strike REAL,
      expiry TEXT, entry_bid REAL, entry_ask REAL, entry_iv REAL, entry_delta REAL, ab_book TEXT,
      payload TEXT)''')
    con.execute('''CREATE TABLE IF NOT EXISTS debriefs(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, trade_date TEXT, q1 TEXT, q2 TEXT, q3 TEXT)''')
    con.execute('''CREATE TABLE IF NOT EXISTS account_snapshots(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, equity REAL, cash REAL, portfolio_value REAL,
      last_equity REAL, buying_power REAL, options_buying_power REAL, daytrade_count INTEGER, payload TEXT)''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_account_snapshots_ts ON account_snapshots(ts)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_trades_dates ON trades(trade_date, status, exit_filled_at)')
    con.commit(); con.close()
    _log_split_development_ledger()

def event(msg,level='INFO'):
    try:
        con=db(); con.execute('INSERT INTO events(ts,level,message,code) VALUES(?,?,?,?)',(now_ny().isoformat(),level,msg,classify_error(msg) if level in ('WARN','ERROR') else None)); con.commit(); con.close()
    except Exception:
        pass
    try:
        print(f'[{level}] {msg}',flush=True)
    except (BrokenPipeError, OSError):
        # A detached terminal must never kill the trading runner. Persistent events
        # above remain available even if stdout has disappeared.
        pass

def meta_get(k):
    con=db(); r=con.execute('SELECT v FROM meta WHERE k=?',(k,)).fetchone(); con.close(); return r['v'] if r else None

def meta_set(k,v):
    con=db(); con.execute('INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v',(k,str(v))); con.commit(); con.close()

def avg(a): return sum(a)/len(a) if a else float('nan')

def wilson_interval(k, n, z=1.96):
    """Wilson 95% CI for a binomial rate. Shows uncertainty when n is small."""
    if not n: return None, None
    p=k/n; z2=z*z; den=1+z2/n
    center=(p+z2/(2*n))/den
    margin=z*math.sqrt((p*(1-p)+z2/(4*n))/n)/den
    return round(max(0.0,center-margin),4), round(min(1.0,center+margin),4)

def sample_label(n):
    if n<10: return 'COLLECTING'
    if n<30: return 'UNDERPOWERED'
    return 'STABLE'
def sma(a,n): return avg(a[-n:]) if len(a)>=n else None
def sd(a): return statistics.stdev(a) if len(a)>=2 else None

def ema_series(vals,n):
    if not vals:return []
    alpha=2/(n+1); out=[vals[0]]
    for x in vals[1:]: out.append(alpha*x+(1-alpha)*out[-1])
    return out

def rsi_simple(vals,n):
    if len(vals)<n+1:return None
    ds=[vals[i]-vals[i-1] for i in range(len(vals)-n,len(vals))]
    g=sum(max(x,0) for x in ds)/n; l=sum(max(-x,0) for x in ds)/n
    if l==0:return 100.0 if g>0 else 50.0
    return 100-100/(1+g/l)

def atr(bars,n=20):
    if len(bars)<n+1:return None
    trs=[]
    for i in range(len(bars)-n,len(bars)):
        h=float(bars[i]['h']); l=float(bars[i]['l']); pc=float(bars[i-1]['c']); trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return avg(trs)

def next_trading_date(d):
    x=datetime.strptime(d,'%Y-%m-%d').date()+timedelta(days=1)
    while x.weekday()>=5:x+=timedelta(days=1)
    return x.isoformat()

def fetch_bars(sym,start,end,timeframe='1Day',feed='iex'):
    out=[]; token=None; guard=0
    while guard<50:
        p={'timeframe':timeframe,'start':start,'end':end,'limit':10000,'adjustment':'all','feed':feed}
        if token:p['page_token']=token
        j=getj(f'{MD}/v2/stocks/{sym}/bars',ah(),p); out+=j.get('bars',[]); token=j.get('next_page_token'); guard+=1
        if not token:break
    return sorted(out,key=lambda x:x['t'])

def fetch_bars_multi(symbols,start,end,timeframe='1Min',feed='iex'):
    out={s:[] for s in symbols}; token=None; guard=0
    while guard<50:
        p={'symbols':','.join(symbols),'timeframe':timeframe,'start':start,'end':end,'limit':10000,'adjustment':'all','feed':feed}
        if token:p['page_token']=token
        j=getj(f'{MD}/v2/stocks/bars',ah(),p)
        bars=j.get('bars') or {}
        if isinstance(bars,list):
            for b in bars:
                s=b.get('S') or b.get('symbol')
                if s: out.setdefault(s,[]).append(b)
        else:
            for s,arr in bars.items(): out.setdefault(s,[]).extend(arr or [])
        token=j.get('next_page_token'); guard+=1
        if not token:break
    for s in list(out): out[s]=sorted(out[s],key=lambda x:x['t'])
    return out

def bar_trade_date(b):
    try:return datetime.fromisoformat(b['t'].replace('Z','+00:00')).astimezone(NY).date().isoformat()
    except:return None

def upsert_live_bars(ticker,timeframe,bars):
    if not bars:return 0
    con=db(); n=0; now=now_ny().isoformat()
    for b in bars:
        td=bar_trade_date(b)
        if not td:continue
        con.execute('''INSERT INTO live_bars(ingested_at,trade_date,ticker,timeframe,t,o,h,l,c,v,vw,n)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(ticker,timeframe,t) DO UPDATE SET
                       ingested_at=excluded.ingested_at,o=excluded.o,h=excluded.h,l=excluded.l,
                       c=excluded.c,v=excluded.v,vw=excluded.vw,n=excluded.n''',
                    (now,td,ticker,timeframe,b['t'],float(b.get('o') or 0),float(b.get('h') or 0),
                     float(b.get('l') or 0),float(b.get('c') or 0),float(b.get('v') or 0),
                     float(b.get('vw') or 0) if b.get('vw') is not None else None,int(b.get('n') or 0)))
        n+=1
    con.commit(); con.close(); return n

def load_local_bars(ticker,trade_date,timeframe='1Min'):
    con=db()
    rows=con.execute('''SELECT t,o,h,l,c,v,vw,n FROM live_bars
                        WHERE ticker=? AND trade_date=? AND timeframe=? ORDER BY t''',
                     (ticker,trade_date,timeframe)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def load_local_bars_since(ticker,timeframe,start_date):
    con=db()
    rows=con.execute('''SELECT t,o,h,l,c,v,vw,n,trade_date FROM live_bars
                        WHERE ticker=? AND timeframe=? AND trade_date>=? ORDER BY t''',
                     (ticker,timeframe,start_date)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def latest_local_bar_t(ticker,timeframe,trade_date=None):
    con=db()
    if trade_date:
        r=con.execute("SELECT t FROM live_bars WHERE ticker=? AND timeframe=? AND trade_date=? ORDER BY t DESC LIMIT 1",(ticker,timeframe,trade_date)).fetchone()
    else:
        r=con.execute("SELECT t FROM live_bars WHERE ticker=? AND timeframe=? ORDER BY t DESC LIMIT 1",(ticker,timeframe)).fetchone()
    con.close(); return r['t'] if r else None

def local_bar_counts(trade_date,timeframe='1Min'):
    con=db()
    rows=con.execute("SELECT ticker,COUNT(*) n FROM live_bars WHERE trade_date=? AND timeframe=? GROUP BY ticker",(trade_date,timeframe)).fetchall()
    con.close(); return {r['ticker']:r['n'] for r in rows}

def expected_session_minutes(date, until=None):
    until=until or now_ny()
    start=datetime.strptime(date,'%Y-%m-%d').replace(hour=9,minute=30,second=0,microsecond=0,tzinfo=NY)
    hard=datetime.strptime(date,'%Y-%m-%d').replace(hour=16,minute=0,second=0,microsecond=0,tzinfo=NY)
    end=min(until.replace(second=0,microsecond=0), hard)
    if end<start: return []
    out=[]; t=start
    while t<=end:
        out.append(t); t+=timedelta(minutes=1)
    return out

def _bar_hm(t):
    return datetime.fromisoformat(str(t).replace('Z','+00:00')).astimezone(NY).strftime('%H:%M')

def _to_z(dt):
    return dt.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H:%M:%SZ')

def _merge_gap_ranges(times, pad_minutes=3):
    if not times: return []
    times=sorted(times); a=b=times[0]; out=[]
    for t in times[1:]:
        if t<=b+timedelta(minutes=pad_minutes):
            b=t
        else:
            out.append((a,b)); a=b=t
    out.append((a,b)); return out

def session_gaps(symbols, date=None, refresh_minutes=None):
    """Completed RTH minutes missing from SQLite (to backfill) vs the forming tail (always refresh)."""
    date=date or now_ny().date().isoformat()
    n=now_ny(); hm=n.strftime('%H:%M')
    in_rth=n.weekday()<5 and '09:30'<=hm<='16:00'
    if refresh_minutes is None: refresh_minutes=2 if in_rth else 0
    expected=expected_session_minutes(date, n)
    refresh_cut=n.replace(second=0,microsecond=0)-timedelta(minutes=max(0,refresh_minutes-1))
    exp_hm={t.strftime('%H:%M') for t in expected}
    coverage={}; ranges_by_sym={}
    con=db()
    for s in symbols:
        rows=con.execute("SELECT t FROM live_bars WHERE ticker=? AND trade_date=? AND timeframe='1Min'",(s,date)).fetchall()
        have=set()
        for r in rows:
            try: have.add(_bar_hm(r['t']))
            except Exception: continue
        holes={r['hm'] for r in con.execute("SELECT hm FROM live_bar_holes WHERE ticker=? AND trade_date=?",(s,date)).fetchall()}
        completed_missing=[]
        for t in expected:
            hm=t.strftime('%H:%M')
            if refresh_minutes and t>=refresh_cut: continue
            if hm not in have and hm not in holes: completed_missing.append(t)
        have_n=len(have & exp_hm); empty_n=len(holes & exp_hm); exp_n=len(expected)
        resolved=min(exp_n, have_n+empty_n)
        coverage[s]={
            'have':have_n,'empty':empty_n,'expected':exp_n,'missing':max(0,exp_n-resolved),
            'pct':round(resolved/exp_n,4) if exp_n else 1.0,
            'first_missing':completed_missing[0].strftime('%H:%M') if completed_missing else None
        }
        ranges_by_sym[s]=_merge_gap_ranges(completed_missing)
    con.close()
    return coverage, ranges_by_sym, refresh_cut if refresh_minutes else None

def session_coverage(symbols, date=None):
    coverage,_,_=session_gaps(symbols, date)
    return coverage

def coverage_avg(coverage):
    pcts=[x['pct'] for x in (coverage or {}).values() if x.get('expected')]
    return round(sum(pcts)/len(pcts),4) if pcts else None

def _fetch_upsert_minutes(symbols, start, end):
    stored=0; ok=[]
    if not symbols or not start or not end: return 0, []
    try:
        multi=fetch_bars_multi(symbols,start,end,'1Min','iex')
        for sym,bars in multi.items(): stored+=upsert_live_bars(sym,'1Min',bars)
        ok=list(symbols)
    except Exception as e:
        event(f'Live bar ingest {start}→{end}: {e}','WARN')
        for sym in symbols:
            try:
                stored+=upsert_live_bars(sym,'1Min',fetch_bars(sym,start,end,'1Min','iex'))
                ok.append(sym)
            except Exception as e2: event(f'Live bars {sym}: {e2}','WARN')
    return stored, ok

def mark_absent_minutes(symbols, date, start, end):
    """After a successful range fetch, remember completed minutes IEX did not return so we never re-query them."""
    if not symbols: return
    t=start.replace(second=0,microsecond=0); minutes=[]
    while t<=end:
        hm=t.strftime('%H:%M')
        if '09:30'<=hm<='16:00': minutes.append(hm)
        t+=timedelta(minutes=1)
    if not minutes: return
    con=db(); now=now_ny().isoformat()
    for s in symbols:
        rows=con.execute("SELECT t FROM live_bars WHERE ticker=? AND trade_date=? AND timeframe='1Min'",(s,date)).fetchall()
        have=set()
        for r in rows:
            try: have.add(_bar_hm(r['t']))
            except Exception: continue
        for hm in minutes:
            if hm not in have:
                con.execute("INSERT OR IGNORE INTO live_bar_holes(ticker,trade_date,hm,probed_at) VALUES(?,?,?,?)",(s,date,hm,now))
    con.commit(); con.close()

def session_bounds_utc(date):
    start=datetime.strptime(date,'%Y-%m-%d').replace(hour=9,minute=25,second=0,tzinfo=NY).astimezone(ZoneInfo('UTC'))
    end=datetime.strptime(date,'%Y-%m-%d').replace(hour=16,minute=5,second=0,tzinfo=NY).astimezone(ZoneInfo('UTC'))
    return start.strftime('%Y-%m-%dT%H:%M:%SZ'), end.strftime('%Y-%m-%dT%H:%M:%SZ')

def rth_bars(bars,cutoff=None):
    out=[]
    for b in bars:
        try:dt=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY)
        except:continue
        hm=dt.strftime('%H:%M')
        if dt.weekday()>=5 or hm<'09:30' or hm>'16:00':continue
        if cutoff and hm>cutoff:continue
        out.append(b)
    return out

def resample_5m(minbars):
    buckets={}
    for b in minbars:
        try:dt=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY)
        except:continue
        key=dt.replace(minute=dt.minute-dt.minute%5,second=0,microsecond=0)
        x=buckets.setdefault(key,{'o':float(b['o']),'h':float(b['h']),'l':float(b['l']),'c':float(b['c']),'v':0.0,'pv':0.0})
        h=float(b['h']); l=float(b['l']); c=float(b['c']); v=float(b.get('v') or 0)
        x['h']=max(x['h'],h); x['l']=min(x['l'],l); x['c']=c; x['v']+=v
        vw=b.get('vw'); x['pv']+=(float(vw)*v if vw else ((h+l+c)/3)*v)
    out=[]
    for k in sorted(buckets):
        x=buckets[k]
        out.append({'t':k.isoformat(),'o':x['o'],'h':x['h'],'l':x['l'],'c':x['c'],'v':x['v'],
                    'vw':(x['pv']/x['v'] if x['v'] else None)})
    return out

def session_vwap(bars):
    pv=0.0; vv=0.0
    for b in bars:
        v=float(b.get('v') or 0)
        if v<=0:continue
        vw=b.get('vw')
        typical=float(vw) if vw not in (None,'') else (float(b['h'])+float(b['l'])+float(b['c']))/3
        pv+=typical*v; vv+=v
    return pv/vv if vv else None

def opening_range(bars):
    or_bars=rth_bars(bars,'09:59')
    or_bars=[b for b in or_bars if datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY).strftime('%H:%M')<'10:00']
    if not or_bars:return None,None,0
    return max(float(b['h']) for b in or_bars), min(float(b['l']) for b in or_bars), sum(float(b.get('v') or 0) for b in or_bars)

def daily_cache_missing(symbols=None,min_sessions=90):
    symbols=symbols or ALL_TICKERS
    date=now_ny().date().isoformat()
    con=db(); missing=[]
    for sym in symbols:
        n=con.execute("SELECT COUNT(*) n FROM live_bars WHERE ticker=? AND timeframe='1Day' AND trade_date<?",(sym,date)).fetchone()['n']
        if (n or 0)<max(20,int(min_sessions)): missing.append(sym)
    con.close()
    return missing

def ensure_daily_cache(symbols=None,min_sessions=90):
    if not keys_ok(): return
    symbols=symbols or ALL_TICKERS
    date=now_ny().date().isoformat()
    min_sessions=max(20,min(365,int(min_sessions)))
    missing=daily_cache_missing(symbols,min_sessions)
    if not missing and meta_get('daily_cache_'+date)=='1': return
    fetch_syms=missing or list(symbols)
    start=(now_ny().date()-timedelta(days=max(120,min_sessions*2))).isoformat()+'T00:00:00Z'
    end=now_ny().isoformat()
    try:
        multi=fetch_bars_multi(fetch_syms,start,end,'1Day','iex')
        for sym,bars in multi.items(): upsert_live_bars(sym,'1Day',bars)
        if not daily_cache_missing(symbols,min_sessions): meta_set('daily_cache_'+date,'1')
    except Exception as e:
        event(f'Daily cache ingest: {e}','WARN')
        for sym in fetch_syms:
            try: upsert_live_bars(sym,'1Day',fetch_bars(sym,start,end,'1Day','iex'))
            except Exception as e2: event(f'Daily cache {sym}: {e2}','WARN')
        if not daily_cache_missing(symbols,min_sessions): meta_set('daily_cache_'+date,'1')

def ensure_minute_history(symbols=None,days=25):
    """Once per day, backfill recent 1Min history into SQLite so 15:45 RVOL does not re-download 38 days."""
    if not keys_ok(): return {'note':'need keys'}
    symbols=symbols or ALL_TICKERS
    date=now_ny().date().isoformat()
    if meta_get('minute_hist_'+date)=='1':return {'note':'cached'}
    con=db(); n=con.execute("SELECT COUNT(DISTINCT trade_date) n FROM live_bars WHERE timeframe='1Min'").fetchone()['n']; con.close()
    if (n or 0)>=18:
        meta_set('minute_hist_'+date,'1'); return {'note':'enough-local','days':n}
    start=(now_ny().date()-timedelta(days=days)).isoformat()+'T13:25:00Z'
    end=now_ny().isoformat(); stored=0
    try:
        multi=fetch_bars_multi(symbols,start,end,'1Min','iex')
        for sym,bars in multi.items(): stored+=upsert_live_bars(sym,'1Min',bars)
        meta_set('minute_hist_'+date,'1')
        event(f'Minute history cached {stored} bars / {days}d')
    except Exception as e:
        event(f'Minute history ingest: {e}','WARN')
    return {'stored':stored}

def kick_minute_history():
    """Backfill 1Min history without blocking the midday scan."""
    global _HIST_THREAD
    date=now_ny().date().isoformat()
    if meta_get('minute_hist_'+date)=='1': return
    if _HIST_THREAD and _HIST_THREAD.is_alive(): return
    def _run():
        try: ensure_minute_history()
        except Exception as e: event(f'Minute history: {e}','WARN')
    _HIST_THREAD=threading.Thread(target=_run,daemon=True,name='minute-hist')
    _HIST_THREAD.start()

def ingest_live_data(symbols=None,force=False):
    """Keep a full RTH session locally. Fetch only missing completed minutes + the forming tail."""
    n=now_ny(); date=n.date().isoformat(); hm=n.strftime('%H:%M')
    if not keys_ok(): return {'note':'need keys','date':date,'bars':0}
    if n.weekday()>=5 and not force: return {'note':'weekend','date':date,'bars':0}
    if not force and (hm<'09:25' or hm>'16:10'): return {'note':'outside rth','date':date,'bars':0}
    last=meta_get('last_ingest')
    if last and not force:
        try:
            if (n-datetime.fromisoformat(last)).total_seconds()<20:
                return {'note':'fresh','date':date,'bars':int(meta_get('last_ingest_bars') or 0),'source':'throttle'}
        except Exception: pass
    symbols=symbols or ALL_TICKERS
    _,end=session_bounds_utc(date)
    end=min(end, n.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H:%M:%SZ'))
    coverage,ranges_by_sym,refresh_cut=session_gaps(symbols,date)
    stored=0; gap_windows=0
    groups={}
    for sym,rngs in ranges_by_sym.items():
        for rng in rngs: groups.setdefault(rng,[]).append(sym)
    for (a,b),group in groups.items():
        n_up,ok=_fetch_upsert_minutes(group,_to_z(a),_to_z(b+timedelta(minutes=1)))
        stored+=n_up
        if ok: mark_absent_minutes(ok,date,a,b)
        gap_windows+=1
    if refresh_cut is not None:
        n_up,_=_fetch_upsert_minutes(symbols,_to_z(refresh_cut),end)
        stored+=n_up
    source='session-gap' if gap_windows else 'tail'
    quotes={}
    snap_key='snapshots|'+','.join(symbols)
    raw=cache_get(snap_key,15)
    if raw is None:
        try:
            raw=getj(f'{MD}/v2/stocks/snapshots',ah(),{'symbols':','.join(symbols),'feed':'iex'})
            cache_set(snap_key,raw)
        except Exception as e:
            event(f'Live quote ingest: {e}','WARN'); raw={}
    try:
        con=db(); ts=n.isoformat(); bucket=n.strftime('%H:%M')
        for sym,snap in (raw or {}).items():
            if not isinstance(snap,dict):continue
            q=snap.get('latestQuote') or {}; t=snap.get('latestTrade') or {}
            bid=q.get('bp'); ask=q.get('ap'); lastp=t.get('p')
            con.execute('DELETE FROM live_quotes WHERE ticker=? AND trade_date=? AND ts LIKE ?',(sym,date,n.strftime('%Y-%m-%dT%H:%M')+'%'))
            con.execute('''INSERT INTO live_quotes(ts,trade_date,ticker,bid,ask,last,bid_sz,ask_sz,payload)
                           VALUES(?,?,?,?,?,?,?,?,?)''',
                        (ts,date,sym,bid,ask,lastp,q.get('bs'),q.get('as'),json.dumps(snap,default=str)))
            quotes[sym]={'bid':bid,'ask':ask,'last':lastp,'bid_sz':q.get('bs'),'ask_sz':q.get('as')}
        con.execute("DELETE FROM live_quotes WHERE trade_date<?",( (n.date()-timedelta(days=3)).isoformat(),))
        con.commit(); con.close()
    except Exception as e:
        event(f'Live quote store: {e}','WARN')
    ensure_daily_cache(symbols)
    overview=build_local_live_overview(date,quotes)
    persist_live_files(date,overview)
    coverage=session_coverage(symbols,date)
    avg_pct=coverage_avg(coverage)
    meta_set('last_ingest',n.isoformat()); meta_set('last_ingest_bars',stored); meta_set('last_ingest_source',source)
    if avg_pct is not None: meta_set('session_coverage_pct',str(avg_pct))
    return {'date':date,'bars':stored,'tickers':len(overview.get('tickers') or {}),'quotes':len(quotes),
            'source':source,'gap_windows':gap_windows,'coverage':coverage,'session_complete_pct':avg_pct}

def persist_live_files(date,overview):
    d=LIVE_DIR/date; d.mkdir(parents=True,exist_ok=True)
    (d/'tape.json').write_text(json.dumps(overview,indent=2))
    for tk,st in (overview.get('tickers') or {}).items():
        (d/f'{tk}.json').write_text(json.dumps(st,indent=2))

def compact_state(s):
    skip={'daily','closes','highs','lows','session','bars_1m','bars_5m','bars5'}
    out={}
    for k,v in s.items():
        if k in skip:continue
        if isinstance(v,float):
            out[k]=None if (v!=v) else round(v,6)
        else: out[k]=v
    return out

def interpret_live(s):
    notes=[]
    or_high,or_low,c=s.get('or_high'),s.get('or_low'),s.get('c')
    if or_high and or_low and c:
        if c>or_high: notes.append('above opening range')
        elif c<or_low: notes.append('below opening range')
        else: notes.append('inside opening range')
    vwap=s.get('vwap'); dist=s.get('vwap_dist_atr')
    if vwap and c:
        side='above' if c>=vwap else 'below'
        notes.append(f'{side} VWAP')
        if dist is not None and abs(dist)>=1.25: notes.append(f'stretched {abs(dist):.2f} ATR from VWAP')
    rv=s.get('rvol')
    if rv is not None: notes.append('elevated volume' if rv>=1.2 else 'normal/light volume')
    rsi=s.get('rsi5')
    if rsi is not None:
        if rsi<30: notes.append('5m RSI oversold')
        elif rsi>70: notes.append('5m RSI overbought')
    gap=s.get('gap_pct'); pc=s.get('prev_close'); rec=s.get('reclaim')
    if gap is not None:
        notes.append(f"gap {gap*100:+.2f}%")
        if pc and c:
            if gap>0 and c>=pc: notes.append('gap-up still holding')
            elif gap<0 and c<=pc: notes.append('gap-down still holding')
            elif gap>0 and c<pc: notes.append('gap-up already given back')
            elif gap<0 and c>pc: notes.append('gap-down already given back')
    if rec=='UP': notes.append('VWAP reclaim from below')
    elif rec=='DOWN': notes.append('lost VWAP from above')
    return notes

def local_intraday_state(sym,date=None):
    date=date or now_ny().date().isoformat()
    mins=rth_bars(load_local_bars(sym,date,'1Min'))
    if not mins: return None
    o=float(mins[0]['o']); h=max(float(x['h']) for x in mins); l=min(float(x['l']) for x in mins)
    c=float(mins[-1]['c']); vol=sum(float(x.get('v') or 0) for x in mins)
    vwap=session_vwap(mins); or_high,or_low,or_vol=opening_range(mins)
    bars5=resample_5m(mins); closes5=[float(x['c']) for x in bars5]
    rsi5=rsi_simple(closes5,14) if len(closes5)>=15 else None
    at=atr(bars5,14) if len(bars5)>=15 else None
    vwap_dist_atr=((c-vwap)/at) if (vwap and at) else None
    con=db()
    drows=con.execute('''SELECT t,o,h,l,c,v FROM live_bars WHERE ticker=? AND timeframe='1Day' AND trade_date<? ORDER BY t''',
                      (sym,date)).fetchall()
    con.close()
    daily=[dict(x) for x in drows]
    prev_close=float(daily[-1]['c']) if daily else None
    avg20=avg([float(x['v']) for x in daily[-20:]]) if len(daily)>=20 else None
    last_dt=datetime.fromisoformat(str(mins[-1]['t']).replace('Z','+00:00')).astimezone(NY)
    elapsed=max(1,(last_dt.hour*60+last_dt.minute)-(9*60+30))
    frac=min(1.0,elapsed/390)
    rvol=(vol/(avg20*frac)) if (avg20 and frac>=0.05) else None
    ret=(c/prev_close-1) if prev_close else None
    gap_pct=(o/prev_close-1) if prev_close else None
    reclaim=None
    if vwap and len(mins)>=8:
        cs=[float(x['c']) for x in mins[-30:]]
        was_below=any(x<vwap for x in cs[:-3]); was_above=any(x>vwap for x in cs[:-3])
        if was_below and c>vwap: reclaim='UP'
        elif was_above and c<vwap: reclaim='DOWN'
    last_q=None
    con=db(); q=con.execute('SELECT bid,ask,last,bid_sz,ask_sz,ts FROM live_quotes WHERE ticker=? AND trade_date=? ORDER BY id DESC LIMIT 1',(sym,date)).fetchone(); con.close()
    if q: last_q=dict(q)
    state={'sym':sym,'date':date,'o':o,'h':h,'l':l,'c':c,'vol':vol,'vwap':vwap,'or_high':or_high,'or_low':or_low,
           'or_width_pct':((or_high-or_low)/((or_high+or_low)/2)*100) if or_high and or_low and or_high>or_low else None,
           'rvol':rvol,'rsi5':rsi5,'atr5':at,'vwap_dist_atr':vwap_dist_atr,'ret':ret,'prev_close':prev_close,
           'gap_pct':gap_pct,'reclaim':reclaim,
           'cp':(c-l)/(h-l) if h>l else .5,'bars':len(mins),'last_bar':mins[-1]['t'],'quote':last_q,
           'clock':last_dt.strftime('%H:%M'),'feed':'iex-local','bars5':bars5[-36:]}
    first_out=None; outside_open=False
    if or_high and or_low:
        for b in mins:
            try: hm=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY).strftime('%H:%M')
            except Exception: continue
            if hm<'10:00': continue
            px=float(b['c']); out=px>or_high or px<or_low
            if hm<='10:05' and out: outside_open=True
            if out and first_out is None: first_out=hm
    state['or_first_break']=first_out; state['or_outside_at_open']=outside_open
    state['or_locked']=last_dt.strftime('%H:%M')>='10:00'
    state['vwap_hi']=(vwap+at) if (vwap and at) else None
    state['vwap_lo']=(vwap-at) if (vwap and at) else None
    rv=rvol or 0; dist=abs(vwap_dist_atr or 0)
    if rv>=1.4 and dist>=1.0: state['regime']='TREND'
    elif rv<0.85 and dist<0.6: state['regime']='CHOP'
    elif rv>=1.2: state['regime']='HIGH_VOLUME'
    else: state['regime']='MIXED'
    state['read']=interpret_live(state)
    return state

def build_local_live_overview(date=None,quotes=None):
    date=date or now_ny().date().isoformat()
    coverage=session_coverage(ALL_TICKERS,date)
    tickers={}
    for sym in ALL_TICKERS:
        st=local_intraday_state(sym,date)
        if not st:continue
        if quotes and quotes.get(sym): st['quote']=quotes[sym]
        row=compact_state(st)
        cov=coverage.get(sym) or {}
        row['bars_have']=cov.get('have'); row['bars_expected']=cov.get('expected'); row['session_pct']=cov.get('pct')
        row['setup']=setup_proximity(st)
        row['regime']=st.get('regime')
        row['or_first_break']=st.get('or_first_break'); row['or_outside_at_open']=st.get('or_outside_at_open')
        row['or_locked']=st.get('or_locked'); row['vwap_hi']=st.get('vwap_hi'); row['vwap_lo']=st.get('vwap_lo')
        b5=st.get('bars5') or []
        row['bars5']=[{'t':x.get('t'),'o':x.get('o'),'h':x.get('h'),'l':x.get('l'),'c':x.get('c')} for x in b5[-36:]]
        tickers[sym]=row
    lasts=[]
    for row in tickers.values():
        dt=parse_ny(row.get('last_bar'))
        if dt: lasts.append(dt)
    freshest=max(lasts) if lasts else None
    if freshest:
        for row in tickers.values():
            dt=parse_ny(row.get('last_bar'))
            if dt and (freshest-dt).total_seconds()>120:
                row['halt']=True
                reasons=row.get('read') or []
                if 'halt / no prints' not in reasons: row['read']=list(reasons)+['halt / no prints']
    clock=session_clock()
    sig_idx=today_signal_index(date); traded=today_traded_index(date)
    for row in tickers.values():
        s=dict(row.get('setup') or {})
        s['why']=setup_why(row, s)
        book=setup_book(s, row.get('sym'), sig_idx, traded)
        s['book']=book.get('state'); s['book_label']=book.get('label')
        s['book_status']=book.get('status'); s['skip_reason']=book.get('skip_reason')
        row['setup']=s
    watch=sorted(tickers.values(), key=lambda x:-(x.get('setup') or {}).get('score') or 0)[:5]
    return {'asof':now_ny().isoformat(),'trade_date':date,'source':'local-sqlite','tickers':tickers,
            'live_dir':str(LIVE_DIR/date),'coverage':coverage,'session_complete_pct':coverage_avg(coverage),
            'clock':clock,'watchlist':[{'sym':x.get('sym'),'setup':x.get('setup'),'c':x.get('c'),'ret':x.get('ret'),
                                       'read':x.get('read')} for x in watch]}

def already_signaled(date,strategy_id,ticker):
    con=db(); r=con.execute("""SELECT id FROM signals WHERE trade_date=? AND strategy_id=? AND ticker=?
                               AND IFNULL(execution_status,'PENDING') NOT IN ('ERROR') LIMIT 1""",
                            (date,strategy_id,ticker)).fetchone(); con.close()
    return bool(r)

def already_traded(date,strategy_id,ticker):
    con=db(); r=con.execute("""SELECT id FROM trades WHERE trade_date=? AND strategy_id=? AND ticker=?
                               AND IFNULL(status,'') NOT IN ('ERROR') LIMIT 1""",
                            (date,strategy_id,ticker)).fetchone(); con.close()
    return bool(r)

def today_signal_index(date):
    con=db(); rows=con.execute("""SELECT ticker,strategy_id,ts,window,direction,execution_status,note FROM signals
                                  WHERE trade_date=? AND IFNULL(execution_status,'PENDING') NOT IN ('ERROR')
                                  ORDER BY id DESC""",(date,)).fetchall(); con.close()
    idx={}
    for r in rows:
        key=(r['strategy_id'], r['ticker'])
        if key not in idx: idx[key]=dict(r)
    return idx

def today_traded_index(date):
    con=db(); rows=con.execute("""SELECT DISTINCT strategy_id,ticker FROM trades
                                  WHERE trade_date=? AND IFNULL(status,'') NOT IN ('ERROR')""",(date,)).fetchall(); con.close()
    return {(r['strategy_id'], r['ticker']) for r in rows}

def setup_why(row, setup):
    """One English tape line for the active sleeve. Prefer reclaim/stretch tags over generic volume."""
    read=list(row.get('read') or [])
    win=(setup or {}).get('window'); side=(setup or {}).get('side')
    prefer=[]
    if win=='VRC':
        prefer=['lost VWAP from above'] if side=='PUT' else (['VWAP reclaim from below'] if side=='CALL' else ['lost VWAP from above','VWAP reclaim from below'])
    elif win=='MVR':
        prefer=['stretched ','5m RSI oversold','5m RSI overbought']
    elif win=='ORB':
        prefer=['above opening range','below opening range']
    elif win=='OPN':
        prefer=['gap-up still holding','gap-down still holding']
    elif win=='OSF':
        prefer=['already given back']
    for tag in read:
        for p in prefer:
            if tag==p or (p.endswith(' ') and tag.startswith(p.strip())) or (p in tag):
                return tag
    skip={'inside opening range','normal/light volume','elevated volume'}
    for tag in read:
        if tag in skip or str(tag).startswith('gap '): continue
        return tag
    bn=(setup or {}).get('bottleneck_en') or (setup or {}).get('bottleneck')
    if bn and bn not in ('FIRED','this setup is at the fire line'): return bn
    return None

def setup_book(setup, ticker, sig_idx, traded):
    """Tape armed ≠ order. Label what the sender already did today for this sleeve/name."""
    sid=(setup or {}).get('window')
    empty={'state':'none','label':None,'status':None,'skip_reason':None}
    if not sid or not ticker: return empty
    sig=(sig_idx or {}).get((sid, ticker))
    if sig:
        st=sig.get('execution_status') or ''
        skip=None
        try: skip=(json.loads(sig.get('note') or '{}') or {}).get('skip_reason')
        except Exception: skip=None
        hm=None
        if sig.get('window') and len(str(sig.get('window')))==5 and str(sig.get('window'))[2]==':':
            hm=str(sig.get('window'))
        else:
            dt=parse_ny(sig.get('ts'))
            if dt: hm=dt.strftime('%H:%M')
        if st in ('ENTRY_SUBMITTED','OPEN','CLOSED','EXIT_SUBMITTED','SIGNAL_ONLY'):
            other=bool(setup.get('side') and sig.get('direction') and sig.get('direction')!=setup.get('side'))
            if other:
                return {'state':'held','label':'no order · already traded today','status':st,'skip_reason':None}
            return {'state':'sent','label':(f'sent {hm}' if hm else 'sent'),'status':st,'skip_reason':None}
        if str(st).startswith('SKIP_'):
            if st=='SKIP_DAILY_CAP':
                label=f'no order · {sid} {skip}' if skip else f'no order · {sid} daily cap'
            elif st=='SKIP_CLUSTER':
                label=f'no order · {skip}' if skip else 'no order · cluster'
            elif st=='SKIP_OPPOSITE':
                label=f'no order · {skip}' if skip else 'no order · open opposite'
            else:
                label=f'no order · {skip}' if skip else f'no order · {st}'
            return {'state':'blocked','label':label,'status':st,'skip_reason':skip}
        return {'state':'signaled','label':st,'status':st,'skip_reason':skip}
    if traded and (sid, ticker) in traded:
        return {'state':'held','label':'no order · already traded today','status':None,'skip_reason':None}
    if (setup or {}).get('fired'):
        return {'state':'armed','label':'armed · waiting on sender','status':None,'skip_reason':None}
    return {'state':'watch','label':None,'status':None,'skip_reason':None}

def open_opposite(ticker, direction):
    """Direction of an OPEN row on this ticker if it is the other side. Else None."""
    if not ticker or not direction: return None
    con=db(); rows=con.execute("SELECT direction FROM trades WHERE ticker=? AND status IN ('ENTRY_SUBMITTED','OPEN','EXIT_SUBMITTED')",(ticker,)).fetchall(); con.close()
    for r in rows:
        d=r['direction']
        if d and d!=direction: return d
    return None

def rank_signals(signals):
    return sorted(list(signals or []), key=lambda s: (-float(s.get('score') or 0), s.get('strategy_id') or '', s.get('ticker') or ''))

def attach_broker_mark(d, pos=None):
    """Live mark only on open rows. Closed rows keep stored pnl — never inherit another ticket's contract."""
    d=dict(d); st=d.get('status')
    if st in OPEN_TRADE_STATUSES:
        p=(pos or {}).get(d.get('option_symbol') or '') if pos else None
        if p:
            try: d['mark']=float(p.get('current_price') or 0)
            except Exception: pass
            try: d['unrealized_pl']=float(p.get('unrealized_pl') or 0)
            except Exception: pass
            try: d['unrealized_plpc']=float(p.get('unrealized_plpc') or 0)
            except Exception: pass
    elif st=='CLOSED':
        d['mark']=d.get('exit_fill')
        d['unrealized_pl']=d.get('pnl')
        d['unrealized_plpc']=None
    return d

def desk_cutoff(days=None):
    days=int(days if days is not None else DESK_WINDOW_DAYS)
    days=max(1,min(days,365))
    return (now_ny().date()-timedelta(days=days)).isoformat()

def trade_date_fields(tr):
    """Keep the Activity dates the desk actually uses, as ISO strings."""
    def day(v):
        s=str(v or '').strip()
        return s[:10] if len(s)>=10 else (s or None)
    return {
        'trade_date':day(tr.get('trade_date')),
        'signal_ts':tr.get('signal_ts'),
        'entry_filled_at':tr.get('entry_filled_at'),
        'exit_filled_at':tr.get('exit_filled_at'),
        'expiry':day(tr.get('expiry')),
        'exit_due_date':day(tr.get('exit_due_date')),
    }

def desk_trades(days=None, pos=None):
    """Open tickets plus anything dated in the rolling window. Older closed rows stay in SQLite."""
    cutoff=desk_cutoff(days)
    placeholders=','.join('?'*len(OPEN_TRADE_STATUSES))
    con=db()
    rows=[dict(x) for x in con.execute(
        f"""SELECT * FROM trades WHERE status IN ({placeholders})
            OR IFNULL(trade_date,'')>=?
            OR IFNULL(substr(exit_filled_at,1,10),'')>=?
            OR IFNULL(substr(signal_ts,1,10),'')>=?
            ORDER BY id DESC""",
        (*OPEN_TRADE_STATUSES,cutoff,cutoff,cutoff)).fetchall()]
    con.close()
    if pos is None:
        try: pos={x.get('symbol'):x for x in broker_positions()}
        except Exception: pos={}
    out=[]
    for r in rows:
        item=attach_broker_mark(dict(r), pos)
        item['dates']=trade_date_fields(item)
        out.append(item)
    return out,cutoff

def stored_account():
    raw=meta_get('account_snapshot')
    if raw:
        try:
            d=json.loads(raw)
            if isinstance(d,dict) and (d.get('equity') is not None or d.get('portfolio_value') is not None):
                d.setdefault('source','snapshot')
                return d
        except Exception:
            pass
    con=db(); row=con.execute('SELECT * FROM account_snapshots ORDER BY id DESC LIMIT 1').fetchone(); con.close()
    if not row: return {'source':'none'}
    d=dict(row)
    try: extra=json.loads(d.get('payload') or '{}')
    except Exception: extra={}
    if not isinstance(extra,dict): extra={}
    for k in ('equity','cash','portfolio_value','last_equity','buying_power','options_buying_power','daytrade_count'):
        if d.get(k) is not None: extra[k]=d.get(k)
    extra['source']='snapshot'
    extra['snapshot_at']=d.get('ts')
    extra['ts']=d.get('ts')
    return extra

def snapshot_account(acct=None):
    a=acct if acct is not None else broker_account()
    ts=now_ny().isoformat()
    compact={k:a.get(k) for k in ('id','status','currency','cash','portfolio_value','equity',
                                  'last_equity','buying_power','options_buying_power','daytrade_count',
                                  'pattern_day_trader','trading_blocked')}
    compact['ts']=ts
    compact['snapshot_at']=ts
    con=db()
    con.execute('''INSERT INTO account_snapshots(ts,equity,cash,portfolio_value,last_equity,buying_power,options_buying_power,daytrade_count,payload)
                   VALUES(?,?,?,?,?,?,?,?,?)''',
                (ts,a.get('equity'),a.get('cash'),a.get('portfolio_value'),a.get('last_equity'),
                 a.get('buying_power'),a.get('options_buying_power'),a.get('daytrade_count'),
                 json.dumps(compact,default=str)))
    con.execute('DELETE FROM account_snapshots WHERE ts<?',(desk_cutoff(),))
    con.commit(); con.close()
    meta_set('account_snapshot',json.dumps(compact,default=str))
    meta_set('account_snapshot_at',ts)
    return compact

def maybe_snapshot_account(acct=None, min_age=60):
    last=meta_get('account_snapshot_at')
    if last and min_age:
        dt=parse_ny(last)
        if dt and (now_ny()-dt).total_seconds()<min_age:
            return None
    try:
        return snapshot_account(acct)
    except Exception as e:
        event(f'Account snapshot: {e}','WARN')
        return None

def live_or_stored_account():
    try:
        a=broker_account()
        maybe_snapshot_account(a)
        out=dict(a); out['source']='live'; out['snapshot_at']=now_ny().isoformat(); return out
    except Exception:
        return stored_account()

def balance_curve(days=None):
    cutoff=desk_cutoff(days)
    con=db()
    rows=[dict(x) for x in con.execute(
        'SELECT ts,equity,cash,portfolio_value FROM account_snapshots WHERE ts>=? ORDER BY ts',
        (cutoff,)).fetchall()]
    con.close()
    if len(rows)<=240: return [{'t':r['ts'],'equity':r['equity'],'cash':r['cash'],'portfolio_value':r['portfolio_value']} for r in rows]
    step=max(1,len(rows)//180)
    sampled=rows[::step]
    if sampled[-1] is not rows[-1]: sampled.append(rows[-1])
    return [{'t':r['ts'],'equity':r['equity'],'cash':r['cash'],'portfolio_value':r['portfolio_value']} for r in sampled]

def fredj(path,p):
    c=cfg(); key=c.get('fred_key')
    if not key:raise RuntimeError('FRED key missing')
    return getj(FRED+path,params={**p,'api_key':key,'file_type':'json'})

def latest_vix():
    hit=cache_get('fred:vix',600)
    if hit: return tuple(hit)
    end=now_ny().date(); start=end-timedelta(days=15)
    j=fredj('/series/observations',{'series_id':'VIXCLS','observation_start':start.isoformat(),'observation_end':end.isoformat()})
    vals=[]
    for x in j.get('observations',[]):
        try:vals.append((x['date'],float(x['value'])))
        except:pass
    out=vals[-1] if vals else (None,None)
    cache_set('fred:vix',list(out)); return out

def macro_dates(start,end):
    out=set()
    for rid in (10,50):
        try:
            j=fredj('/release/dates',{'release_id':rid,'realtime_start':start,'realtime_end':end,'include_release_dates_with_no_data':'true','limit':1000})
            out.update(x['date'] for x in j.get('release_dates',[]) if x.get('date'))
        except Exception as e:event(f'Macro release lookup {rid}: {e}','WARN')
    out.update({'2026-01-28','2026-03-18','2026-04-29','2026-06-17','2026-07-29','2026-09-16','2026-10-28','2026-12-09'})
    out.update(cfg().get('fomc_dates',[])); return out

def ny_sessions(minbars,cutoff='15:45'):
    s={}
    for b in minbars:
        try:dt=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY)
        except:continue
        hm=dt.strftime('%H:%M')
        if dt.weekday()<5 and '09:30'<=hm<=cutoff:s.setdefault(dt.date().isoformat(),[]).append(b)
    for d in s:s[d].sort(key=lambda x:x['t'])
    return s

def build_market_state():
    n=now_ny(); date=n.date().isoformat(); states={}
    ingest_live_data(); ensure_daily_cache(TICKERS); ensure_minute_history(TICKERS,30)
    start_d=(n.date()-timedelta(days=38)).isoformat()
    for sym in TICKERS:
        daily=load_local_bars_since(sym,'1Day',(n.date()-timedelta(days=400)).isoformat())
        if len(daily)<210:
            daily=fetch_bars(sym,(n.date()-timedelta(days=340)).isoformat()+'T00:00:00Z',n.isoformat(),'1Day','iex')
            upsert_live_bars(sym,'1Day',daily)
        mins=load_local_bars_since(sym,'1Min',start_d)
        if not rth_bars([b for b in mins if bar_trade_date(b)==date] or load_local_bars(sym,date,'1Min')):
            try:
                s0,e0=session_bounds_utc(date)
                upsert_live_bars(sym,'1Min',fetch_bars(sym,s0,n.isoformat(),'1Min','iex'))
                mins=load_local_bars_since(sym,'1Min',start_d)
            except Exception as e: event(f'{sym} today minutes: {e}','WARN')
        sessions=ny_sessions(mins,'15:45'); today=sessions.get(date,[])
        if not today:raise RuntimeError(f'{sym}: no live IEX minute bars for {date}')
        completed=[b for b in daily if (b.get('trade_date') or b['t'][:10])<date]
        if len(completed)<210:raise RuntimeError(f'{sym}: insufficient daily history')
        o=float(today[0]['o']); h=max(float(x['h']) for x in today); l=min(float(x['l']) for x in today); c=float(today[-1]['c']); vol=sum(float(x.get('v',0) or 0) for x in today)
        prior_dates=sorted(d for d in sessions if d<date); base=prior_dates[-20:]
        if len(base)<20:
            # fall back to time-adjusted daily volume like midday, still logged
            avg20=avg([float(x.get('v') or 0) for x in completed[-20:]]) if len(completed)>=20 else None
            elapsed=max(1,(datetime.fromisoformat(str(today[-1]['t']).replace('Z','+00:00')).astimezone(NY).hour*60+datetime.fromisoformat(str(today[-1]['t']).replace('Z','+00:00')).astimezone(NY).minute)-(9*60+30))
            frac=min(1.0,elapsed/390); rvol=(vol/(avg20*frac)) if (avg20 and frac>=0.05) else None
        else:
            basevol=avg([sum(float(x.get('v',0) or 0) for x in sessions[d]) for d in base]); rvol=vol/basevol if basevol else None
        closes=[float(b['c']) for b in completed]+[c]; prev_close=float(completed[-1]['c']); ret=c/prev_close-1
        last1500=[]
        for b in today:
            dt=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY)
            if dt.strftime('%H:%M')>='15:00':last1500.append(b)
        ret45=(c/float(last1500[0]['o'])-1) if last1500 else 0
        states[sym]={'sym':sym,'date':date,'o':o,'h':h,'l':l,'c':c,'vol':vol,'rvol':rvol,'cp':(c-l)/(h-l) if h>l else .5,'closes':closes,'daily':completed,'ret':ret,'ret45':ret45,'rsi3':rsi_simple(closes,3),'rsi2':rsi_simple(closes,2),'feed':'iex-local','bars':len(today),'session_pct':1.0}
    return states

def stochastic(state):
    bars=state['daily'][-16:]+[{'h':state['h'],'l':state['l'],'c':state['c']}]
    if len(bars)<15:return None,None,None,None
    def kat(i):
        sub=bars[i-13:i+1]; hh=max(float(x['h']) for x in sub); ll=min(float(x['l']) for x in sub); cc=float(bars[i]['c']); return 50 if hh==ll else 100*(cc-ll)/(hh-ll)
    ks=[kat(i) for i in range(13,len(bars))]
    if len(ks)<4:return None,None,None,None
    return ks[-2],avg(ks[-4:-1]),ks[-1],avg(ks[-3:])

def strategy_signals(states):
    out=[]
    try:vix_date,vix=latest_vix()
    except Exception as e:vix_date,vix=None,None;event(f'VIX unavailable: {e}','WARN')
    tomorrow=next_trading_date(now_ny().date().isoformat()); macros=macro_dates((now_ny().date()-timedelta(days=2)).isoformat(),(now_ny().date()+timedelta(days=10)).isoformat()); macro_clear=tomorrow not in macros
    def add(sid,ticker,direction,score,details):out.append({'strategy_id':sid,'ticker':ticker,'direction':direction,'score':float(score),'details':details})
    for sym,s in states.items():
        c=s['c']; closes=s['closes']; daily=s['daily']; cp=s['cp']; rv=s['rvol'] or 0
        if s['rsi3'] is not None and s['rsi3']<15 and cp<.30 and rv>1.2 and vix is not None and vix>=15 and macro_clear:add('CEG',sym,'CALL',1,{'rsi3':s['rsi3'],'cp':cp,'rvol':rv,'vix':vix})
        body=abs(c-s['o']); lower=min(s['o'],c)-s['l']
        if c>s['o'] and lower>1.5*max(body,.01) and rv>1.2:add('VCT',sym,'CALL',lower/max(body,.01),{'lower_shadow':lower,'body':body,'rvol':rv})
        others=[x for k,x in states.items() if k!=sym]; div=avg([x['ret'] for x in others])-s['ret']
        if s['rsi3'] is not None and s['rsi3']<20 and cp<.25 and rv>1.2 and div>.0075:add('XED',sym,'CALL',div*100,{'rsi3':s['rsi3'],'cp':cp,'rvol':rv,'divergence_pp':div*100})
        prev5low=min(float(x['l']) for x in daily[-5:])
        if s['l']<prev5low and cp>.70 and s['ret45']>.005 and rv>1.2:add('LAR',sym,'CALL',s['ret45']*100,{'cp':cp,'ret45':s['ret45'],'rvol':rv})
        ma200=sma(closes[:-1],200)
        if ma200 and c>ma200 and s['rsi2'] is not None and s['rsi2']<10:add('RSI2',sym,'CALL',(10-s['rsi2'])/10,{'rsi2':s['rsi2'],'sma200':ma200})
        prev20=closes[-21:-1]
        if len(prev20)==20:
            mid=avg(prev20); sig=sd(prev20)
            if sig:
                lo=mid-2*sig; hi=mid+2*sig
                if c<lo:add('BB',sym,'CALL',(lo-c)/sig,{'mid':mid,'lower':lo,'upper':hi})
                elif c>hi:add('BB',sym,'PUT',(c-hi)/sig,{'mid':mid,'lower':lo,'upper':hi})
        if len(closes)>=40:
            e12=ema_series(closes,12); e26=ema_series(closes,26); mac=[a-b for a,b in zip(e12,e26)]; sl=ema_series(mac,9)
            if mac[-2]<=sl[-2] and mac[-1]>sl[-1]:add('MACD',sym,'CALL',mac[-1]-sl[-1],{'macd':mac[-1],'signal':sl[-1]})
            elif mac[-2]>=sl[-2] and mac[-1]<sl[-1]:add('MACD',sym,'PUT',sl[-1]-mac[-1],{'macd':mac[-1],'signal':sl[-1]})
        hi20=max(float(x['h']) for x in daily[-20:]); lo20=min(float(x['l']) for x in daily[-20:])
        if c>hi20:add('DON',sym,'CALL',(c/hi20-1)*100,{'prior20_high':hi20})
        elif c<lo20:add('DON',sym,'PUT',(lo20/c-1)*100,{'prior20_low':lo20})
        kp,dp,kn,dn=stochastic(s)
        if None not in (kp,dp,kn,dn):
            if kp<=dp and kn>dn and kn<25:add('STO',sym,'CALL',(25-kn)/25,{'k':kn,'d':dn})
            elif kp>=dp and kn<dn and kn>75:add('STO',sym,'PUT',(kn-75)/25,{'k':kn,'d':dn})
        at=atr(daily[-30:]+[{'h':s['h'],'l':s['l'],'c':c}],20)
        if len(closes)>=25 and at:
            em20=ema_series(closes,20)[-1]; up=em20+2*at; low=em20-2*at
            if c>up:add('KEL',sym,'CALL',(c-up)/at,{'ema20':em20,'atr20':at})
            elif c<low:add('KEL',sym,'PUT',(low-c)/at,{'ema20':em20,'atr20':at})
    return out,{'vix':vix,'vix_date':vix_date,'macro_clear_tomorrow':macro_clear}

def midday_signals(states, which='ALL', ignore_clock=False):
    """Intraday strategies from locally stored minute bars. One signal per strategy/ticker/day."""
    out=[]; evals=[]; hm=now_ny().strftime('%H:%M')
    def on(sid,start,end):
        if which not in ('ALL','BOTH',sid): return False
        return ignore_clock or start<=hm<=end
    run_opn=on('OPN','09:35','09:55'); run_osf=on('OSF','09:50','10:25')
    run_orb=on('ORB','10:05','11:30'); run_vrc=on('VRC','10:30','13:00'); run_mvr=on('MVR','11:00','14:30')
    def add(sid,ticker,direction,score,details,reason='FIRED',book='A'):
        details={**details,'clock':hm,'ab_book':book}
        out.append({'strategy_id':sid,'ticker':ticker,'direction':direction,'score':float(score),
                    'details':details,'horizon':'EOD','window':hm,'session_window':sid,'ab_book':book})
        evals.append({'strategy_id':sid,'ticker':ticker,'window':sid,'eligible':1,'direction':direction,
                      'score':float(score),'reason':reason,'metrics':details})
    def miss(sid,ticker,reason,metrics):
        evals.append({'strategy_id':sid,'ticker':ticker,'window':sid,'eligible':0,'direction':None,
                      'score':None,'reason':reason,'metrics':metrics})
    for sym,s in states.items():
        book,th=ab_book(sym)
        c=s.get('c'); rv=s.get('rvol') or 0; pc=s.get('prev_close'); gap=s.get('gap_pct')
        metrics={**compact_state(s),'ab_book':book}
        if run_opn:
            gneed=th.get('opn_gap',0.0035)
            if (s.get('bars') or 0)<5: miss('OPN',sym,'too early in the open',metrics)
            elif gap is None or pc is None: miss('OPN',sym,'need prior close for gap',metrics)
            elif abs(gap)<gneed: miss('OPN',sym,f'gap {gap*100:.2f}% < {gneed*100:.2f}%',metrics)
            elif rv<th.get('opn_rvol',1.0): miss('OPN',sym,f'rvol {rv:.2f} < {th.get("opn_rvol",1.0)}',metrics)
            elif gap>0 and c>=pc:
                add('OPN',sym,'CALL',abs(gap)*100,{'gap_pct':gap,'prev_close':pc,'rvol':rv,'hold':'gap-up holding'},book=book)
            elif gap<0 and c<=pc:
                add('OPN',sym,'PUT',abs(gap)*100,{'gap_pct':gap,'prev_close':pc,'rvol':rv,'hold':'gap-down holding'},book=book)
            else: miss('OPN',sym,'gap already given back (OSF territory)',metrics)
        if run_osf:
            gneed=th.get('osf_gap',0.0035)
            if gap is None or pc is None: miss('OSF',sym,'need prior close for gap',metrics)
            elif abs(gap)<gneed: miss('OSF',sym,f'gap {gap*100:.2f}% too small to fade',metrics)
            elif rv<0.8: miss('OSF',sym,f'rvol {rv:.2f} < 0.8',metrics)
            elif gap>0 and c<pc:
                add('OSF',sym,'PUT',abs(gap)*100,{'gap_pct':gap,'prev_close':pc,'rvol':rv,'fail':'gap-up lost prior close'},book=book)
            elif gap<0 and c>pc:
                add('OSF',sym,'CALL',abs(gap)*100,{'gap_pct':gap,'prev_close':pc,'rvol':rv,'fail':'gap-down lost prior close'},book=book)
            else: miss('OSF',sym,'gap still holding (OPN territory)',metrics)
        if run_orb:
            orh,orl,width=s.get('or_high'),s.get('or_low'),s.get('or_width_pct')
            bars=s.get('bars') or 0
            if bars<28 or orh is None or orl is None: miss('ORB',sym,'opening range incomplete',metrics)
            elif width is not None and width<0.12: miss('ORB',sym,'range too tight',metrics)
            elif width is not None and width>1.9: miss('ORB',sym,'range too wide / chaos day',metrics)
            elif rv<th['orb_rvol']: miss('ORB',sym,f'rvol {rv:.2f} < {th["orb_rvol"]}',metrics)
            elif c>orh:
                if s.get('or_outside_at_open') and (s.get('or_first_break') or '10:05')<='10:05':
                    miss('ORB',sym,'still outside range (not first break)',metrics)
                else:
                    add('ORB',sym,'CALL',(c/orh-1)*100,{'or_high':orh,'or_low':orl,'rvol':rv,'width_pct':width,'read':s.get('read'),'first_break':s.get('or_first_break')},book=book)
            elif c<orl:
                if s.get('or_outside_at_open') and (s.get('or_first_break') or '10:05')<='10:05':
                    miss('ORB',sym,'still outside range (not first break)',metrics)
                else:
                    add('ORB',sym,'PUT',(orl/c-1)*100,{'or_high':orh,'or_low':orl,'rvol':rv,'width_pct':width,'read':s.get('read'),'first_break':s.get('or_first_break')},book=book)
            else: miss('ORB',sym,'inside opening range',metrics)
        if run_vrc:
            rec=s.get('reclaim'); dist=s.get('vwap_dist_atr'); vwap=s.get('vwap')
            if vwap is None or dist is None: miss('VRC',sym,'need VWAP',metrics)
            elif rec not in ('UP','DOWN'): miss('VRC',sym,'no VWAP reclaim yet',metrics)
            elif rv<th.get('vrc_rvol',0.9): miss('VRC',sym,f'rvol {rv:.2f} < {th.get("vrc_rvol",0.9)}',metrics)
            elif abs(dist)<th.get('vrc_atr',0.2): miss('VRC',sym,f'reclaim only {dist:.2f} ATR through VWAP',metrics)
            elif rec=='UP':
                add('VRC',sym,'CALL',abs(dist),{'vwap':vwap,'vwap_dist_atr':dist,'reclaim':rec,'rvol':rv},book=book)
            else:
                add('VRC',sym,'PUT',abs(dist),{'vwap':vwap,'vwap_dist_atr':dist,'reclaim':rec,'rvol':rv},book=book)
        if run_mvr:
            dist=s.get('vwap_dist_atr'); rsi=s.get('rsi5'); vwap=s.get('vwap')
            stretch,lo,hi=th['mvr_stretch'],th['mvr_rsi_lo'],th['mvr_rsi_hi']
            if vwap is None or dist is None or rsi is None: miss('MVR',sym,'need VWAP + 5m ATR/RSI',metrics)
            elif rv<th['mvr_rvol']: miss('MVR',sym,f'rvol {rv:.2f} < {th["mvr_rvol"]}',metrics)
            elif dist<=-stretch and rsi<=lo:
                add('MVR',sym,'CALL',abs(dist),{'vwap':vwap,'vwap_dist_atr':dist,'rsi5':rsi,'rvol':rv,'read':s.get('read')},book=book)
            elif dist>=stretch and rsi>=hi:
                add('MVR',sym,'PUT',abs(dist),{'vwap':vwap,'vwap_dist_atr':dist,'rsi5':rsi,'rvol':rv,'read':s.get('read')},book=book)
            elif abs(dist)<stretch: miss('MVR',sym,f'not stretched vs VWAP ({dist:.2f} ATR)',metrics)
            else: miss('MVR',sym,f'RSI {rsi:.1f} not extreme with stretch {dist:.2f}',metrics)
    return out,evals,{'clock':hm,'opn':run_opn,'osf':run_osf,'orb':run_orb,'vrc':run_vrc,'mvr':run_mvr}

def option_quote(symbol):
    if not symbol: return {}
    try:
        j=getj_cached(f'{MD}/v1beta1/options/quotes/latest',ah(),{'symbols':symbol},ttl=8,key='oq:'+symbol)
        q=(j.get('quotes') or {}).get(symbol) or (j.get('quote') if isinstance(j.get('quote'),dict) else {})
        if not q and isinstance(j.get('quotes'),dict):
            q=next(iter(j['quotes'].values()),{})
        bid=q.get('bp') or q.get('bid_price'); ask=q.get('ap') or q.get('ask_price')
        ts=q.get('t') or q.get('timestamp')
        age=None
        dt=parse_ny(ts)
        if dt: age=(now_ny()-dt).total_seconds()
        return {'bid':bid,'ask':ask,'spread':(float(ask)-float(bid)) if bid not in (None,0) and ask else None,
                'ts':ts,'age_sec':age}
    except Exception:
        return {}

def contract_quality(spot, strike, expiry, direction, quote, style):
    notes=[]; score=100.0
    try: dte=(datetime.strptime(str(expiry)[:10],'%Y-%m-%d').date()-now_ny().date()).days
    except Exception: dte=None
    moneyness=(style or {}).get('moneyness') or ''
    if dte==0:
        score-=25; notes.append('0DTE')
    elif dte is not None and dte<=1:
        score-=10; notes.append(f'{dte}DTE')
    if spot:
        otm=abs(float(strike)-float(spot))/float(spot)
        if otm>0.012:
            score-=min(40, otm*800); notes.append(f'{otm*100:.1f}% from spot')
    spr=quote.get('spread'); mid=None
    if quote.get('bid') and quote.get('ask'):
        mid=(float(quote['bid'])+float(quote['ask']))/2
        if mid>0 and spr is not None and spr/mid>0.25:
            score-=20; notes.append('wide option spread')
        elif mid>0 and spr is not None and spr/mid>0.12:
            score-=8; notes.append('elevated option spread')
    if moneyness=='otm1': score-=12; notes.append('otm1')
    grade='A' if score>=80 else 'B' if score>=65 else 'C' if score>=50 else 'D'
    return {'score':round(max(0,score),1),'grade':grade,'dte':dte,'notes':notes,'quote':quote}

def pretrade_checklist(sig, states, coverage, quote, quality):
    date=now_ny().date().isoformat(); sid=sig['strategy_id']; ticker=sig['ticker']
    st=states.get(ticker) or {}; cov=(coverage or {}).get(ticker) or {}
    items=[]
    def add(ok,label,detail=''):
        items.append({'ok':bool(ok),'label':label,'detail':detail})
    add((cov.get('pct') or st.get('session_pct') or 0)>=0.9 or (st.get('bars') or 0)>=30, 'tape coverage', f"{int((cov.get('pct') or st.get('session_pct') or 0)*100)}%")
    add(not already_traded(date,sid,ticker), 'not already traded today')
    add((st.get('session_pct') or cov.get('pct') or 1)>=0.9, 'session complete enough')
    add(quality.get('grade') in ('A','B'), 'contract grade A/B', quality.get('grade'))
    spr=quote.get('spread'); mid=None
    if quote.get('bid') and quote.get('ask'): mid=(float(quote['bid'])+float(quote['ask']))/2
    add(not (mid and spr and spr/mid>0.35), 'option spread usable')
    add(not do_not_trade_reasons(st, st.get('quote')), 'not on do-not-trade list')
    add(st.get('c') is not None, 'spot available')
    age=quote.get('age_sec')
    add(age is None or age<=thresh()['quote_max_age_sec'], 'option quote fresh', None if age is None else f'{age:.0f}s')
    return {'pass':all(x['ok'] for x in items),'items':items}

def do_not_trade_reasons(s, quote=None):
    reasons=[]
    if (s.get('session_pct') or 1)<0.9: reasons.append('incomplete tape')
    q=quote or s.get('quote') or {}
    bid,ask,last=q.get('bid'),q.get('ask'),q.get('last') or s.get('c')
    try:
        if bid and ask and last and (float(ask)-float(bid))/float(last)>0.004: reasons.append('wide underlying spread')
    except Exception: pass
    if s.get('bars') is not None and (s.get('bars') or 0)<30: reasons.append('thin session')
    if s.get('halt'): reasons.append('halt / no prints')
    try:
        if last and s.get('c') and abs(float(last)-float(s['c']))/float(s['c'])>0.002:
            reasons.append('quote/tape divergence')
    except Exception: pass
    earn=earnings_block(s.get('sym'))
    if earn: reasons.append(earn)
    return reasons

def classify_error(msg):
    m=(msg or '').lower()
    if '429' in m or 'too many' in m: return 'RATE_LIMIT'
    if 'lock' in m: return 'SQLITE_LOCK'
    if 'no active' in m or 'contract' in m: return 'NO_CONTRACT'
    if '401' in m or '403' in m or 'unauthorized' in m: return 'AUTH'
    if 'reject' in m or 'expired' in m or 'canceled' in m: return 'BROKER_REJECT'
    if 'timeout' in m or 'connect' in m or 'network' in m: return 'NETWORK'
    return 'OTHER'

def daily_fire_count(sid, date=None):
    date=date or now_ny().date().isoformat()
    con=db(); n=con.execute("""SELECT COUNT(*) n FROM trades WHERE strategy_id=? AND trade_date=?
                               AND IFNULL(status,'') NOT IN ('ERROR')""",(sid,date)).fetchone()['n']; con.close()
    return n or 0

def cluster_count(date=None, window_min=20):
    date=date or now_ny().date().isoformat()
    con=db(); rows=con.execute("SELECT signal_ts FROM trades WHERE trade_date=? AND IFNULL(status,'') NOT IN ('ERROR')",(date,)).fetchall(); con.close()
    n=now_ny(); cut=n-timedelta(minutes=window_min); k=0
    for r in rows:
        dt=parse_ny(r['signal_ts'])
        if dt and dt>=cut: k+=1
    return k

def hyp_atm_pnl(tr, last_und, entry_und):
    """Delta-0.5 ATM overlay vs actual option P&L. Not a fill."""
    if not last_und or not entry_und: return None
    move=last_und-entry_und
    if tr.get('direction')=='PUT': move=-move
    qty=int(tr.get('qty') or 1)
    return round(50.0*qty*move, 2)

def notify_once(key, text):
    if meta_get(key)=='1': return
    maybe_notify(text); meta_set(key,'1')

def bootstrap_expectancy(pnls, n=800):
    if len(pnls)<3: return None
    means=[]
    for _ in range(n):
        samp=[pnls[random.randrange(len(pnls))] for _ in range(len(pnls))]
        means.append(sum(samp)/len(samp))
    means.sort()
    return {'p05':round(means[int(0.05*n)],4),'p50':round(means[n//2],4),'p95':round(means[int(0.95*n)],4),
            'frac_positive':round(sum(1 for m in means if m>0)/n,4),'n':len(pnls)}

def earnings_block(ticker, date=None):
    date=date or now_ny().date().isoformat()
    raw=(cfg().get('earnings_dates') or {}).get(ticker) or (cfg().get('earnings_dates') or {}).get(str(ticker).upper())
    if not raw: return None
    dates=raw if isinstance(raw,list) else [raw]
    d0=datetime.strptime(date,'%Y-%m-%d').date()
    for x in dates:
        try:
            dx=datetime.strptime(str(x)[:10],'%Y-%m-%d').date()
        except Exception:
            continue
        if abs((dx-d0).days)<=1:
            return f'earnings {dx.isoformat()}'
    return None

def loser_cooldown(sid, date=None):
    date=date or now_ny().date().isoformat()
    con=db(); r=con.execute("""SELECT pnl FROM trades WHERE strategy_id=? AND trade_date=? AND status='CLOSED'
                               ORDER BY id DESC LIMIT 1""",(sid,date)).fetchone(); con.close()
    if r and r['pnl'] is not None and float(r['pnl'])<0:
        return True
    return False

def kelly_qty(sid, base=1):
    con=db(); rows=con.execute("SELECT pnl,trade_date FROM trades WHERE strategy_id=? AND status='CLOSED' AND pnl IS NOT NULL",(sid,)).fetchall(); con.close()
    days=len({(r['trade_date'] or '')[:10] for r in rows})
    if days<30:
        return max(1,int(base)), f'qty capped at 1 until nDays≥30 ({days}d)'
    pnls=[float(r['pnl']) for r in rows]
    wins=[p for p in pnls if p>0]; losses=[abs(p) for p in pnls if p<0]
    if not wins or not losses:
        return max(1,int(base)), 'kelly undefined (no win/loss split)'
    wr=len(wins)/len(pnls); b=avg(wins)/avg(losses)
    f=wr-(1-wr)/b
    half=max(0.0, f/2.0)
    qty=max(1, min(5, int(round(int(base)*max(1.0, half/0.25)))))
    if days<30: qty=1
    return qty, f'half-Kelly {half:.3f} wr={wr:.2f} b={b:.2f}'

def pdt_block(horizon):
    if horizon!='EOD':
        return None
    try:
        a=broker_account()
    except Exception:
        return 'PDT risk account unread'
    eq=float(a.get('equity') or a.get('portfolio_value') or 0)
    dtc=int(float(a.get('daytrade_count') or 0))
    pdt=bool(a.get('pattern_day_trader'))
    if eq<25000 and (pdt or dtc>=3):
        return f'PDT risk daytrade_count={dtc} equity={eq:.0f} flagged={int(pdt)}'
    return None

def bp_block(ask, qty):
    if not ask: return 'no option ask for buying-power check'
    debit=float(ask)*100*int(qty or 1)
    try: a=broker_account()
    except Exception: return None
    cash=float(a.get('cash') or 0)
    bp=float(a.get('options_buying_power') or a.get('buying_power') or cash)
    cap=min(cash*thresh()['bp_frac'], bp if bp>0 else cash)
    if debit>cap:
        return f'debit ${debit:.0f} > BP cap ${cap:.0f}'
    return None

def clock_skew():
    try:
        j=getj_cached(paper_api_url('/clock'),ah(),ttl=30,key='broker:clock')
        ts=j.get('timestamp') or j.get('server_time')
        dt=parse_ny(ts)
        if not dt: return {'ok':True,'skew_sec':None,'server':ts}
        skew=(now_ny()-dt).total_seconds()
        return {'ok':abs(skew)<=thresh()['clock_skew_sec'],'skew_sec':round(skew,2),'server':dt.isoformat(),
                'is_open':j.get('is_open')}
    except Exception as e:
        return {'ok':None,'error':str(e)[:160]}

def bar_integrity(date=None):
    date=date or now_ny().date().isoformat()
    out={}
    con=db()
    for sym in ALL_TICKERS:
        rows=con.execute("SELECT t,c FROM live_bars WHERE ticker=? AND trade_date=? AND timeframe='1Min' ORDER BY t",(sym,date)).fetchall()
        blob='|'.join(f"{r['t']}:{r['c']}" for r in rows)
        h=hashlib.sha256(blob.encode()).hexdigest()[:16] if rows else None
        out[sym]={'n':len(rows),'hash':h,'first':rows[0]['t'] if rows else None,'last':rows[-1]['t'] if rows else None}
    con.close()
    return out

def mae_mfe_from_tape(tr):
    """Underlying MAE/MFE from bar high/low vs atm_spot (not close-to-close)."""
    date=tr.get('trade_date') or now_ny().date().isoformat()
    bars=rth_bars(load_local_bars(tr.get('ticker'),date,'1Min'))
    start=parse_ny(tr.get('entry_filled_at') or tr.get('signal_ts'))
    end=parse_ny(tr.get('exit_filled_at')) or now_ny()
    if not start or not bars: return None, None
    entry=None
    try:
        if tr.get('atm_spot') not in (None,''): entry=float(tr['atm_spot'])
    except Exception: entry=None
    hi=None; lo=None
    for b in bars:
        dt=parse_ny(b.get('t'))
        if not dt or dt<start: continue
        if dt>end: break
        try:
            h=float(b['h']); l=float(b['l']); c=float(b['c'])
        except Exception: continue
        if entry is None: entry=c
        hi=h if hi is None else max(hi,h)
        lo=l if lo is None else min(lo,l)
    if entry in (None,0) or hi is None or lo is None: return None, None
    if tr.get('direction')=='PUT':
        mae=min(0.0,(entry-hi)/entry)
        mfe=max(0.0,(entry-lo)/entry)
    else:
        mae=min(0.0,(lo-entry)/entry)
        mfe=max(0.0,(hi-entry)/entry)
    return round(mae,5), round(mfe,5)

def fill_quality(tr):
    fill=tr.get('entry_fill'); ask=tr.get('entry_ask'); bid=tr.get('entry_bid')
    if fill is None or ask in (None,0): return None
    try:
        fill=float(fill); ask=float(ask); bid=float(bid) if bid not in (None,'') else None
    except Exception:
        return None
    would=fill<=ask*1.02
    slip=(fill-ask)/ask if ask else None
    return {'would_fill_at_ask':would,'fill':fill,'ask':ask,'bid':bid,'slip_vs_ask':round(slip,4) if slip is not None else None}

def min_detectable_edge(n, p0=0.5, power=0.8, alpha=0.05):
    """Two-sided MDE on a win-rate vs p0. Uses normal approx (z_a + z_b)*se."""
    if not n: return None
    z_a=1.96 if abs(alpha-0.05)<1e-6 else 1.64
    z_b=0.84 if abs(power-0.8)<1e-6 else 1.28
    se=math.sqrt(p0*(1-p0)/n)
    return round((z_a+z_b)*se,4)

def power_curve(p=0.5):
    rows=[]
    for n in (5,10,20,30,50,80,100,150):
        lo,hi=wilson_interval(int(round(p*n)), n)
        width=(hi-lo) if lo is not None else None
        rows.append({'n':n,'ci_lo':lo,'ci_hi':hi,'ci_width':round(width,4) if width is not None else None,
                     'mde':min_detectable_edge(n,p)})
    return rows

def binom_p_two_sided(wins, n, p0=0.5):
    if not n or n<4: return 1.0
    se=math.sqrt(p0*(1-p0)/n)
    z=abs((wins/n)-p0)/se
    return min(1.0, max(0.0, 2*(1-_ncdf(z))))

def benjamini_hochberg(items, q=0.1):
    """items: list of {id,p}. Returns same with reject + q_star."""
    m=len(items)
    ranked=sorted([(i,x.get('p') if x.get('p') is not None else 1.0) for i,x in enumerate(items)], key=lambda t:t[1])
    cutoff=0
    for rank,(idx,p) in enumerate(ranked,1):
        if p<=q*rank/m: cutoff=rank
    out=[]
    for rank,(idx,p) in enumerate(ranked,1):
        row=dict(items[idx]); row['p']=round(p,4); row['rank']=rank; row['reject']=rank<=cutoff and cutoff>0
        out.append(row)
    out.sort(key=lambda x:x.get('id') or '')
    return out

def loo_fire_rates(rows):
    tickers=sorted({r.get('ticker') for r in rows if r.get('ticker')})
    out=[]
    for tk in tickers:
        sub=[r for r in rows if r.get('ticker')!=tk]
        n=len(sub); f=sum(1 for r in sub if r.get('eligible'))
        out.append({'left_out':tk,'n':n,'fires':f,'fireRate':round(f/n,4) if n else None})
    return out

def seasonality_heatmap(midday):
    grid={d:{h:0 for h in range(9,17)} for d in range(5)}
    fire={d:{h:0 for h in range(9,17)} for d in range(5)}
    for r in midday:
        dt=parse_ny(r.get('ts'))
        if not dt: continue
        wd=dt.weekday(); h=dt.hour
        if wd>4 or h<9 or h>16: continue
        grid[wd][h]+=1
        if r.get('eligible'): fire[wd][h]+=1
    days=['Mon','Tue','Wed','Thu','Fri']
    cells=[]
    for wd in range(5):
        for h in range(9,17):
            n=grid[wd][h]; f=fire[wd][h]
            cells.append({'day':days[wd],'weekday':wd,'hour':h,'n':n,'fires':f,'rate':round(f/n,3) if n else None})
    return cells

def monte_carlo_open_book(open_tr, n=400):
    if not open_tr: return None
    date=now_ny().date().isoformat()
    rets=[]
    for t in open_tr:
        bars=rth_bars(load_local_bars(t.get('ticker'),date,'1Min'))
        cs=[float(b['c']) for b in bars[-90:]]
        for i in range(1,len(cs)):
            if cs[i-1]: rets.append(cs[i]/cs[i-1]-1)
    if len(rets)<10: return None
    premium=0.0
    for t in open_tr:
        try: premium+=float(t.get('entry_fill') or 0)*100*int(t.get('qty') or 1)
        except Exception: pass
    terminal=[]
    for _ in range(n):
        path=1.0
        for __ in range(20):
            path*=(1+rets[random.randrange(len(rets))])
        terminal.append((path-1)*premium*0.5)
    terminal.sort()
    return {'n':n,'p05':round(terminal[int(0.05*n)],2),'p50':round(terminal[n//2],2),'p95':round(terminal[int(0.95*n)],2),
            'premium_at_risk':round(premium,2)}

def log_shadow(sig, status, extra):
    extra=extra or {}
    try:
        q=(extra.get('quality') or {}).get('quote') or {}
        gk=extra.get('greeks') or {}
        con=db(); con.execute('''INSERT INTO shadow_trades(ts,trade_date,strategy_id,ticker,direction,option_symbol,status,skip_reason,spot,strike,expiry,entry_bid,entry_ask,entry_iv,entry_delta,ab_book,payload)
                                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (now_ny().isoformat(),now_ny().date().isoformat(),sig.get('strategy_id'),sig.get('ticker'),
                               sig.get('direction'),extra.get('option'),status,extra.get('skip_reason'),extra.get('spot'),
                               extra.get('strike'),extra.get('expiry'),q.get('bid'),q.get('ask'),gk.get('iv'),gk.get('delta'),
                               extra.get('ab_book') or sig.get('ab_book'), json.dumps(extra,default=str)[:4000]))
        con.commit(); con.close()
    except Exception as e:
        event(f'shadow log: {e}','WARN')

def backup_db(tag='exit'):
    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        stamp=now_ny().strftime('%Y%m%d_%H%M%S')
        dst=BACKUP_DIR/f'arena_{tag}_{stamp}.db'
        if DB.exists():
            # SQLite's online backup API takes a consistent snapshot while the
            # runner continues writing. Copying the database file directly can
            # miss committed pages that still live in the WAL.
            src=sqlite3.connect(f'file:{DB}?mode=ro',uri=True,timeout=30)
            out=sqlite3.connect(dst,timeout=30)
            try: src.backup(out)
            finally:
                out.close(); src.close()
        return str(dst)
    except Exception as e:
        event(f'backup: {e}','WARN'); return None

def client_is_local():
    ip=(request.remote_addr or '')
    return ip in ('127.0.0.1','::1','localhost')

def orders_allowed():
    if cfg().get('allow_lan_orders', False): return True
    try:
        return client_is_local()
    except RuntimeError:
        return True

def submit_exit(tr, kind='SCHEDULE'):
    client=f"x53-{int(tr['id'])}"[:48]
    qty=int(tr['qty'] or 1)
    o=place_broker_order({'symbol':tr['option_symbol'],'qty':str(qty),'side':'sell','type':'market','time_in_force':'day','client_order_id':client})
    con=db(); con.execute("UPDATE trades SET exit_order_id=?,exit_client_id=?,status='EXIT_SUBMITTED',exit_kind=? WHERE id=?",
                          (o.get('id'),client,kind,tr['id'])); con.commit(); con.close()
    event(f"Exit {kind} {tr['strategy_id']} {tr['ticker']} {tr['option_symbol']}")
    return o

def refresh_excursions_and_stops():
    th=thresh(); n=now_ny(); hm=n.strftime('%H:%M')
    con=db(); rows=[dict(x) for x in con.execute("SELECT * FROM trades WHERE status IN ('OPEN','EXIT_SUBMITTED')").fetchall()]; con.close()
    rth='09:30'<=hm<='16:00' and n.weekday()<5
    for tr in rows:
        mae,mfe=mae_mfe_from_tape(tr)
        if mae is not None:
            con=db(); con.execute('UPDATE trades SET mae=?,mfe=? WHERE id=?',(mae,mfe,tr['id'])); con.commit(); con.close()
            tr['mae'],tr['mfe']=mae,mfe
        if not rth or tr.get('status')!='OPEN': continue
        if (tr.get('scaled_qty') or 0)<=0 and (mfe or 0)>=th['scale_mfe']:
            qty=int(tr.get('qty') or 1)
            if qty>=2:
                half=qty//2
                try:
                    client=f"s53-{int(tr['id'])}"[:48]
                    place_broker_order({'symbol':tr['option_symbol'],'qty':str(half),'side':'sell','type':'market','time_in_force':'day','client_order_id':client})
                    con=db(); con.execute('UPDATE trades SET qty=?,scaled_qty=? WHERE id=?',(qty-half,half,tr['id'])); con.commit(); con.close()
                    event(f"Scale-out {tr['strategy_id']} {tr['ticker']} x{half}")
                except Exception as e:
                    event(f'Scale-out {tr["id"]}: {e}','WARN')
            else:
                try:
                    submit_exit(tr, 'SCALE')
                    continue
                except Exception as e:
                    event(f'Scale-out {tr["id"]}: {e}','WARN')
        entry=parse_ny(tr.get('entry_filled_at') or tr.get('signal_ts'))
        held=None if not entry else (now_ny()-entry).total_seconds()/60.0
        sid=tr.get('strategy_id'); horizon=tr.get('horizon') or 'OVERNIGHT'
        date=tr.get('trade_date') or now_ny().date().isoformat()
        st=local_intraday_state(tr.get('ticker'), date) or {}
        und_move=None
        try:
            if tr.get('atm_spot') and st.get('c'):
                und_move=(float(st['c'])-float(tr['atm_spot']))/float(tr['atm_spot'])
                if tr.get('direction')=='PUT': und_move=-und_move
        except Exception: pass
        kind=None
        if horizon=='EOD' and held is not None and held>=th['time_stop_min'] and abs(und_move or 0)<th['min_und_move']:
            kind='TIME'
        elif sid=='ORB' and st.get('or_high') and st.get('or_low') and st.get('c'):
            if st['or_low']<=st['c']<=st['or_high'] and held and held>=15:
                kind='SIGNAL'
        elif sid=='OPN' and st.get('prev_close') and st.get('c') and held and held>=5:
            if tr.get('direction')=='CALL' and st['c']<st['prev_close']: kind='SIGNAL'
            if tr.get('direction')=='PUT' and st['c']>st['prev_close']: kind='SIGNAL'
        elif sid=='OSF' and st.get('prev_close') and st.get('c') and held and held>=5:
            if tr.get('direction')=='PUT' and st['c']>st['prev_close']: kind='SIGNAL'
            if tr.get('direction')=='CALL' and st['c']<st['prev_close']: kind='SIGNAL'
        elif sid=='VRC' and st.get('vwap') and st.get('c') and held and held>=8:
            if tr.get('direction')=='CALL' and st['c']<st['vwap']: kind='SIGNAL'
            if tr.get('direction')=='PUT' and st['c']>st['vwap']: kind='SIGNAL'
        elif sid=='MVR' and st.get('vwap_dist_atr') is not None:
            dist=st['vwap_dist_atr']
            if tr.get('direction')=='CALL' and dist>0.4: kind='SIGNAL'
            if tr.get('direction')=='PUT' and dist<-0.4: kind='SIGNAL'
        if kind and '09:30'<=hm<'15:50':
            try: submit_exit(tr, kind)
            except Exception as e:
                if meta_get(f"stop_err_{tr['id']}")!='1':
                    event(f'{kind} stop trade {tr["id"]}: {e}','ERROR')
                    meta_set(f"stop_err_{tr['id']}",'1')

def strat_opt(sid):
    s=next((x for x in STRATEGIES if x['id']==sid),None)
    return dict((s or {}).get('opt') or {'dte':'next','moneyness':'otm1'})

def option_contract(ticker,direction,spot,allow_0dte=False,style=None):
    style=dict(style or {})
    if allow_0dte and not style.get('dte'): style['dte']='0dte'
    dte=style.get('dte','next'); moneyness=style.get('moneyness','otm1')
    today=now_ny().date()
    if dte=='0dte':
        td=today.isoformat()
        if now_ny().strftime('%H:%M')>='15:50': td=next_trading_date(td)
        end=td
    else:
        td=next_trading_date(today.isoformat())
        end=(datetime.strptime(td,'%Y-%m-%d').date()+timedelta(days=7)).isoformat()
    if moneyness=='atm': target=spot
    elif moneyness=='itm1': target=spot*.99 if direction=='CALL' else spot*1.01
    else: target=spot*1.01 if direction=='CALL' else spot*.99
    band=0.03 if moneyness=='atm' else 0.06
    typ='call' if direction=='CALL' else 'put'
    p={'underlying_symbols':ticker,'status':'active','expiration_date_gte':td,'expiration_date_lte':end,'type':typ,
       'strike_price_gte':f'{spot*(1-band):.2f}','strike_price_lte':f'{spot*(1+band):.2f}','limit':1000}
    j=getj(paper_api_url('/options/contracts'),ah(),p); arr=j.get('option_contracts') or j.get('contracts') or []
    arr=[c for c in arr if isinstance(c,dict) and (c.get('expiration_date') or '')[:10]==td] if dte=='0dte' else list(arr or [])
    if not arr:
        if dte=='0dte':
            raise RuntimeError(f'No same-day {typ} contract for {ticker} exp {td}')
        raise RuntimeError(f'No active {typ} contracts returned for {ticker}')
    if dte=='0dte':
        arr=sorted(arr,key=lambda x:abs(float(x.get('strike_price',0))-target))
    else:
        arr=sorted(arr,key=lambda x:(x.get('expiration_date','9999'),abs(float(x.get('strike_price',0))-target)))
    c=arr[0]
    exp=(c.get('expiration_date') or '')[:10]
    if dte=='0dte' and exp!=td:
        raise RuntimeError(f'same-day contract expiry {exp} != {td}')
    reason=f"{style.get('dte',dte)} {moneyness} target {target:.2f} vs spot {spot:.2f}"
    return c['symbol'],c.get('expiration_date'),float(c.get('strike_price')),reason,style

def log_contract(sid,ticker,direction,spot,symbol,expiry,strike,style,reason):
    try:
        con=db(); con.execute('''INSERT INTO contract_log(ts,trade_date,strategy_id,ticker,direction,spot,strike,expiry,option_symbol,dte,moneyness,reason)
                                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (now_ny().isoformat(),now_ny().date().isoformat(),sid,ticker,direction,spot,strike,expiry,symbol,
                               (style or {}).get('dte'),(style or {}).get('moneyness'),reason)); con.commit(); con.close()
    except Exception as e: event(f'contract log: {e}','WARN')

def submit_entry(sig,states):
    c=cfg(); th=thresh(); sid=sig['strategy_id']; ticker=sig['ticker']; direction=sig['direction']
    horizon=sig.get('horizon','OVERNIGHT'); window=sig.get('window','15:45'); style=strat_opt(sid)
    date=now_ny().date().isoformat()
    book, _thb = ab_book(ticker)
    qty, kelly_note = kelly_qty(sid, int(c.get('contracts_per_trade',1)))
    con=db(); dupe=con.execute("SELECT id FROM trades WHERE strategy_id=? AND ticker=? AND status IN ('ENTRY_SUBMITTED','OPEN','EXIT_SUBMITTED') LIMIT 1",(sid,ticker)).fetchone(); con.close()
    if dupe:return 'SKIP_OPEN_TRADE',None
    opp=open_opposite(ticker, direction)
    if opp:
        extra={'skip_reason':f'open opposite {opp} on {ticker}','ab_book':book}
        event(f'{sid} skip opposite {ticker}','WARN')
        log_shadow(sig,'SKIP_OPPOSITE',extra); return 'SKIP_OPPOSITE',extra
    fires=daily_fire_count(sid,date)
    if fires>=th['max_daily_fires']:
        extra={'skip_reason':f'daily cap {fires}/{th["max_daily_fires"]}','ab_book':book}; event(f'{sid} skip daily cap {ticker}','WARN')
        log_shadow(sig,'SKIP_DAILY_CAP',extra); return 'SKIP_DAILY_CAP',extra
    clus=cluster_count(date,20)
    if clus>=th['max_cluster']:
        extra={'skip_reason':f'cluster {clus} fires in 20m','ab_book':book}; event(f'{sid} skip cluster {ticker}','WARN')
        log_shadow(sig,'SKIP_CLUSTER',extra); return 'SKIP_CLUSTER',extra
    if loser_cooldown(sid,date):
        extra={'skip_reason':'loser cooldown until next session','ab_book':book}
        log_shadow(sig,'SKIP_LOSER',extra); return 'SKIP_LOSER',extra
    pdt=pdt_block(horizon)
    if pdt:
        extra={'skip_reason':pdt,'ab_book':book}; event(f'{sid} skip PDT {ticker}','WARN')
        log_shadow(sig,'SKIP_PDT',extra); return 'SKIP_PDT',extra
    spot=states[ticker]['c']
    coverage=session_coverage(ALL_TICKERS,date)
    st=states[ticker]
    dnt=do_not_trade_reasons(st, st.get('quote'))
    try:
        option,expiry,strike,reason,style=option_contract(ticker,direction,spot,allow_0dte=(horizon=='EOD'),style=style)
    except RuntimeError as e:
        status='SKIP_NO_0DTE' if horizon=='EOD' else 'SKIP_NO_CONTRACT'
        extra={'skip_reason':str(e),'ab_book':book}
        log_shadow(sig,status,extra); return status,extra
    q=option_quote(option)
    quality=contract_quality(spot,strike,expiry,direction,q,style)
    mid=None
    if q.get('bid') and q.get('ask'):
        try: mid=(float(q['bid'])+float(q['ask']))/2
        except Exception: mid=None
    gk=greeks_snap(spot,strike,expiry,mid,direction) if mid else {'iv':None,'delta':None,'gamma':None}
    check=pretrade_checklist(sig,states,coverage,q,quality)
    log_contract(sid,ticker,direction,spot,option,expiry,strike,style,reason)
    extra={'option':option,'expiry':expiry,'strike':strike,'horizon':horizon,'window':window,'spot':spot,'opt':style,
           'reason':reason,'quality':quality,'checklist':check,'cluster_n':clus,'dnt':dnt,'greeks':gk,
           'ab_book':book,'kelly':kelly_note,'qty':qty}
    if dnt:
        extra['skip_reason']=', '.join(dnt); log_shadow(sig,'SKIP_DNT',extra); return 'SKIP_DNT',extra
    if not check['pass'] and quality.get('grade') in ('D',):
        extra['skip_reason']='checklist/contract grade D'; log_shadow(sig,'SKIP_CHECKLIST',extra); return 'SKIP_CHECKLIST',extra
    age=q.get('age_sec')
    if age is not None and age>th['quote_max_age_sec']:
        extra['skip_reason']=f'option quote stale {age:.0f}s'; log_shadow(sig,'SKIP_STALE_QUOTE',extra); return 'SKIP_STALE_QUOTE',extra
    bp=bp_block(q.get('ask'), qty)
    if bp:
        extra['skip_reason']=bp; log_shadow(sig,'SKIP_BP',extra); return 'SKIP_BP',extra
    if not broker_orders_enabled():return 'SIGNAL_ONLY',extra
    if not orders_allowed():
        extra['skip_reason']='guest LAN read-only'; log_shadow(sig,'SKIP_GUEST',extra); return 'SKIP_GUEST',extra
    client=f'a53-{date.replace("-","")}-{sid.lower()}-{ticker.lower()}'[:48]
    o=place_broker_order({'symbol':option,'qty':str(qty),'side':'buy','type':'market','time_in_force':'day','client_order_id':client})
    exit_due=now_ny().date().isoformat() if horizon=='EOD' else next_trading_date(now_ny().date().isoformat())
    con=db(); con.execute('''INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,entry_order_id,entry_client_id,exit_due_date,status,broker_note,horizon,window,entry_bid,entry_ask,entry_spread,contract_score,checklist,cluster_n,atm_spot,entry_iv,entry_delta,entry_gamma,ab_book,greeks)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (sid,ticker,direction,option,qty,now_ny().isoformat(),date,expiry,o.get('id'),client,exit_due,'ENTRY_SUBMITTED','paper market order',horizon,window,
                           q.get('bid'),q.get('ask'),q.get('spread'),quality.get('score'),json.dumps(check,default=str),clus,spot,
                           gk.get('iv'),gk.get('delta'),gk.get('gamma'),book,json.dumps(gk,default=str)))
    con.commit(); tid=con.execute('SELECT last_insert_rowid() x').fetchone()['x']; con.close()
    extra['trade_id']=tid; extra['order_id']=o.get('id'); extra['quality']=quality
    return 'ENTRY_SUBMITTED',extra


def journal_snapshot(states, signals, freeze_time="15:45"):
    """Write an immutable-ish point-in-time record for every ticker and EOD strategies."""
    date=now_ny().date().isoformat()
    fired={(s["strategy_id"],s["ticker"]):s for s in signals}
    con=db()
    for tk,s in states.items():
        payload=compact_state(s)
        con.execute("""INSERT OR IGNORE INTO snapshots(ts,trade_date,ticker,freeze_time,feed,payload)
                       VALUES(?,?,?,?,?,?)""",
                    (now_ny().isoformat(),date,tk,freeze_time,s.get("feed","unknown"),json.dumps(payload,default=str)))
    if freeze_time=="15:45":
        for st in STRATEGIES:
            if st["id"] not in EOD_STRATEGY_IDS: continue
            for tk in TICKERS:
                sig=fired.get((st["id"],tk))
                con.execute("""INSERT INTO strategy_journal(ts,trade_date,strategy_id,ticker,eligible,direction,score,reason,metrics)
                               VALUES(?,?,?,?,?,?,?,?,?)
                               ON CONFLICT(trade_date,strategy_id,ticker) DO UPDATE SET
                               ts=excluded.ts,eligible=excluded.eligible,direction=excluded.direction,
                               score=excluded.score,reason=excluded.reason,metrics=excluded.metrics""",
                            (now_ny().isoformat(),date,st["id"],tk,1 if sig else 0,
                             sig.get("direction") if sig else None,
                             sig.get("score") if sig else None,
                             "FIRED" if sig else "NO SIGNAL",
                             json.dumps(sig.get("details",{}) if sig else {},default=str)))
    con.commit();con.close()

def journal_midday(states, evals, window):
    date=now_ny().date().isoformat(); con=db()
    for tk,s in states.items():
        con.execute("""INSERT INTO snapshots(ts,trade_date,ticker,freeze_time,feed,payload)
                       VALUES(?,?,?,?,?,?)
                       ON CONFLICT(trade_date,ticker,freeze_time,feed) DO UPDATE SET
                       ts=excluded.ts, payload=excluded.payload""",
                    (now_ny().isoformat(),date,tk,window,s.get("feed","iex-local"),json.dumps(compact_state(s),default=str)))
    for e in evals:
        con.execute("""INSERT INTO midday_evals(ts,trade_date,strategy_id,ticker,window,eligible,direction,score,reason,metrics)
                       VALUES(?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(trade_date,strategy_id,ticker,window) DO UPDATE SET
                       ts=excluded.ts,
                       eligible=CASE WHEN midday_evals.eligible=1 THEN 1 ELSE excluded.eligible END,
                       direction=CASE WHEN midday_evals.eligible=1 THEN midday_evals.direction ELSE excluded.direction END,
                       score=CASE WHEN midday_evals.eligible=1 THEN midday_evals.score ELSE excluded.score END,
                       reason=CASE WHEN midday_evals.eligible=1 THEN midday_evals.reason ELSE excluded.reason END,
                       metrics=CASE WHEN midday_evals.eligible=1 THEN midday_evals.metrics ELSE excluded.metrics END""",
                    (now_ny().isoformat(),date,e['strategy_id'],e['ticker'],e.get('window') or window,
                     e['eligible'],e.get('direction'),e.get('score'),e.get('reason'),
                     json.dumps(e.get('metrics') or {},default=str)))
    con.commit(); con.close()

def reconcile():
    con=db(); rows=con.execute("SELECT * FROM trades WHERE status IN ('ENTRY_SUBMITTED','EXIT_SUBMITTED')").fetchall(); con.close()
    for tr in rows:
        oid=tr['entry_order_id'] if tr['status']=='ENTRY_SUBMITTED' else tr['exit_order_id']
        if not oid:continue
        try:o=getj(paper_api_url(f'/orders/{oid}'),ah(),timeout=8)
        except Exception as e:event(f'Order reconcile {oid}: {e}','WARN');continue
        st=o.get('status')
        if st=='filled':
            fp=float(o.get('filled_avg_price') or 0); ft=o.get('filled_at'); con=db()
            if tr['status']=='ENTRY_SUBMITTED':
                con.execute("UPDATE trades SET entry_fill=?,entry_filled_at=?,status='OPEN' WHERE id=?",(fp,ft,tr['id']))
                msg=f"FILLED entry {tr['strategy_id']} {tr['ticker']} {tr['option_symbol']} @ {fp}"
            else:
                pnl=(fp-float(tr['entry_fill'] or 0))*100*int(tr['qty']); con.execute("UPDATE trades SET exit_fill=?,exit_filled_at=?,status='CLOSED',pnl=? WHERE id=?",(fp,ft,pnl,tr['id']))
                try:
                    mae,mfe=mae_mfe_from_tape({**dict(tr),'exit_filled_at':ft,'status':'CLOSED'})
                    if mae is not None: con.execute('UPDATE trades SET mae=?,mfe=? WHERE id=?',(mae,mfe,tr['id']))
                except Exception: pass
                msg=f"CLOSED {tr['strategy_id']} {tr['ticker']} P&L ${pnl:.2f}"
            con.commit(); con.close(); event(msg)
        elif st in ('canceled','expired','rejected'):
            con=db(); con.execute("UPDATE trades SET status='ERROR',broker_note=? WHERE id=?",(f'order {st}',tr['id'])); con.commit(); con.close()
            event(f"Order {st} {tr['strategy_id']} {tr['ticker']} {tr['option_symbol']}",'WARN')

def _client_order_parts(client_id):
    parts=str(client_id or '').split('-')
    if len(parts)<4 or parts[0]!='a53':return None
    if len(parts[1])==8 and parts[1].isdigit():
        return parts[1],parts[2].upper(),parts[3].upper()
    # Legacy a53-SID-TICKER-timestamp ids.
    return None,parts[1].upper(),parts[2].upper()

def _option_direction_expiry(symbol):
    m=re.search(r'(\d{6})([CP])\d{8}$',str(symbol or ''))
    if not m:return None,None
    try: expiry=datetime.strptime(m.group(1),'%y%m%d').date().isoformat()
    except ValueError: expiry=None
    return ('CALL' if m.group(2)=='C' else 'PUT'),expiry

def _broker_symbols(positions):
    if not isinstance(positions,list): return set()
    return {p.get('symbol') for p in positions if isinstance(p,dict) and p.get('symbol')}

def _option_is_worthless(tr, n=None):
    n=n or now_ny(); hm=n.strftime('%H:%M'); today=n.date().isoformat()
    exp=(tr.get('expiry') or '')[:10]
    horizon=tr.get('horizon') or 'OVERNIGHT'
    after_close=n.weekday()>=5 or hm>='16:00'
    if exp and exp<today: return True
    if horizon=='EOD' and after_close: return True
    return False

def _expire_trade(tr, note='expired / no quote after close'):
    n=now_ny()
    fill=float(tr.get('entry_fill') or 0)
    pnl=round(-fill*100*int(tr.get('qty') or 1),2)
    con=db(); con.execute("UPDATE trades SET status='CLOSED',pnl=?,exit_kind='EXPIRED',broker_note=?,exit_filled_at=? WHERE id=?",
                          (pnl,note,n.isoformat(),tr['id']))
    con.commit(); con.close()
    event(f"EXPIRED {tr['strategy_id']} {tr['ticker']} {tr.get('option_symbol')} P&L ${pnl:.2f}")

def _broker_order_time(order):
    return parse_ny(order.get('filled_at') or order.get('submitted_at') or order.get('created_at'))

def _matching_exit_fill(tr, orders, used_order_ids=None, allow_generic=False):
    """Find one broker sell for a local ticket without reusing another ticket's exit.

    Current exits use ``x53-<local id>``. Pre-hardening releases used
    ``x53-<strategy>-<ticker>-<timestamp>``; those fills are still authoritative
    when strategy, ticker, symbol, and chronology agree. Generic x53 matching is
    reserved for repairing a broker round trip whose local row was lost.
    """
    used=set(used_order_ids or ())
    want=str(tr.get('exit_client_id') or '')
    fallback=f"x53-{int(tr['id'])}" if tr.get('id') is not None else ''
    symbol=str(tr.get('option_symbol') or '')
    entry_at=parse_ny(tr.get('entry_filled_at') or tr.get('signal_ts'))

    candidates=[]
    for order in orders or []:
        if not isinstance(order,dict) or order.get('side')!='sell' or str(order.get('status') or '')!='filled':
            continue
        oid=str(order.get('id') or '')
        if not oid or oid in used or order.get('filled_avg_price') is None:
            continue
        if symbol and str(order.get('symbol') or '')!=symbol:
            continue
        filled_at=_broker_order_time(order)
        if entry_at and filled_at and filled_at<entry_at:
            continue
        candidates.append(order)

    def earliest(rows):
        return min(rows,key=lambda o:(_broker_order_time(o) or datetime.max.replace(tzinfo=NY),str(o.get('id') or ''))) if rows else None

    exact=[o for o in candidates if str(o.get('client_order_id') or '') in (want,fallback) and str(o.get('client_order_id') or '')]
    if exact:return earliest(exact)

    sid=str(tr.get('strategy_id') or '').lower()
    ticker=str(tr.get('ticker') or '').lower()
    legacy_prefix=f'x53-{sid}-{ticker}-' if sid and ticker else ''
    legacy=[o for o in candidates if legacy_prefix and str(o.get('client_order_id') or '').lower().startswith(legacy_prefix)]
    if legacy:return earliest(legacy)

    if allow_generic:
        generic=[o for o in candidates if str(o.get('client_order_id') or '').lower().startswith('x53-')]
        return earliest(generic)
    return None

def broker_ledger_repair_plan(orders):
    """Build a deterministic, broker-sourced repair plan without changing SQLite."""
    broker_orders=[o for o in (orders or []) if isinstance(o,dict)]
    con=db(); trades=[dict(r) for r in con.execute('SELECT * FROM trades ORDER BY id').fetchall()]; con.close()
    used_exits={str(t.get('exit_order_id')) for t in trades if t.get('exit_order_id')}
    plan=[]

    # Replace guessed full-premium expirations when Alpaca has the actual sell.
    guessed=sorted(
        (t for t in trades if t.get('status')=='CLOSED' and t.get('exit_kind')=='EXPIRED' and not t.get('exit_order_id')),
        key=lambda t:(parse_ny(t.get('entry_filled_at') or t.get('signal_ts')) or datetime.min.replace(tzinfo=NY),int(t.get('id') or 0)),
    )
    for tr in guessed:
        sell=_matching_exit_fill(tr,broker_orders,used_exits)
        if not sell:continue
        oid=str(sell.get('id') or ''); used_exits.add(oid)
        exit_fill=float(sell.get('filled_avg_price') or 0)
        pnl=(exit_fill-float(tr.get('entry_fill') or 0))*100*int(tr.get('qty') or 1)
        plan.append({
            'action':'update','trade_id':int(tr['id']),'strategy_id':tr.get('strategy_id'),'ticker':tr.get('ticker'),
            'entry_order_id':tr.get('entry_order_id'),'exit_order_id':oid,
            'exit_client_id':sell.get('client_order_id'),'exit_fill':exit_fill,'exit_filled_at':sell.get('filled_at'),
            'pnl':round(pnl,8),'old_pnl':tr.get('pnl'),
        })

    # Recover completed app-managed round trips that disappeared with a local DB
    # replacement. A buy is only rebuilt when an app-managed broker sell proves
    # that the position was closed; flat buys without a matching sell stay out.
    known_entries={str(t.get('entry_order_id')) for t in trades if t.get('entry_order_id')}
    known_clients={str(t.get('entry_client_id')) for t in trades if t.get('entry_client_id')}
    buys=sorted(
        (o for o in broker_orders if o.get('side')=='buy' and str(o.get('status') or '')=='filled'
         and str(o.get('client_order_id') or '').startswith('a53-')),
        key=lambda o:(_broker_order_time(o) or datetime.min.replace(tzinfo=NY),str(o.get('id') or '')),
    )
    for buy in buys:
        oid=str(buy.get('id') or ''); cid=str(buy.get('client_order_id') or '')
        if oid in known_entries or cid in known_clients:continue
        parsed=_client_order_parts(cid)
        if not parsed:continue
        day,sid,ticker=parsed
        submitted=parse_ny(buy.get('submitted_at') or buy.get('created_at')) or now_ny()
        trade_date=(datetime.strptime(day,'%Y%m%d').date().isoformat() if day else submitted.date().isoformat())
        direction,expiry=_option_direction_expiry(buy.get('symbol'))
        probe={
            'strategy_id':sid,'ticker':ticker,'option_symbol':buy.get('symbol'),
            'entry_filled_at':buy.get('filled_at'),'signal_ts':submitted.isoformat(),
        }
        sell=_matching_exit_fill(probe,broker_orders,used_exits,allow_generic=True)
        if not sell:continue
        exit_oid=str(sell.get('id') or ''); used_exits.add(exit_oid)
        qty=int(float(buy.get('filled_qty') or buy.get('qty') or 0))
        if qty<=0:continue
        entry_fill=float(buy.get('filled_avg_price') or 0)
        exit_fill=float(sell.get('filled_avg_price') or 0)
        horizon='EOD' if sid in MIDDAY_STRATEGY_IDS else 'OVERNIGHT'
        exit_due=trade_date if horizon=='EOD' else next_trading_date(trade_date)
        plan.append({
            'action':'insert','strategy_id':sid,'ticker':ticker,'direction':direction,
            'option_symbol':buy.get('symbol'),'qty':qty,'signal_ts':submitted.isoformat(),'trade_date':trade_date,
            'expiry':expiry,'entry_order_id':oid,'entry_client_id':cid,'entry_fill':entry_fill,
            'entry_filled_at':buy.get('filled_at'),'exit_due_date':exit_due,'exit_order_id':exit_oid,
            'exit_client_id':sell.get('client_order_id'),'exit_fill':exit_fill,'exit_filled_at':sell.get('filled_at'),
            'status':'CLOSED','pnl':round((exit_fill-entry_fill)*100*qty,8),'horizon':horizon,
            'window':sid if horizon=='EOD' else '15:45',
        })
    return plan

def apply_broker_ledger_repair(plan):
    """Apply a reviewed repair plan in one short transaction."""
    updated=inserted=0
    con=db()
    try:
        con.execute('BEGIN IMMEDIATE')
        for item in plan or []:
            if item.get('action')=='update':
                cur=con.execute('''UPDATE trades SET exit_order_id=?,exit_client_id=?,exit_fill=?,exit_filled_at=?,
                                   status='CLOSED',pnl=?,exit_kind='BROKER_REPAIR',broker_note=?
                                   WHERE id=? AND exit_order_id IS NULL AND exit_kind='EXPIRED' ''',
                                (item.get('exit_order_id'),item.get('exit_client_id'),item.get('exit_fill'),
                                 item.get('exit_filled_at'),item.get('pnl'),'corrected from Alpaca sell fill',item.get('trade_id')))
                updated+=cur.rowcount
            elif item.get('action')=='insert':
                exists=con.execute('SELECT id FROM trades WHERE entry_order_id=? OR entry_client_id=? LIMIT 1',
                                   (item.get('entry_order_id'),item.get('entry_client_id'))).fetchone()
                if exists:continue
                con.execute('''INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,
                               entry_order_id,entry_client_id,entry_fill,entry_filled_at,exit_due_date,exit_order_id,
                               exit_client_id,exit_fill,exit_filled_at,status,pnl,broker_note,horizon,window,exit_kind)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (item.get('strategy_id'),item.get('ticker'),item.get('direction'),item.get('option_symbol'),
                             item.get('qty'),item.get('signal_ts'),item.get('trade_date'),item.get('expiry'),
                             item.get('entry_order_id'),item.get('entry_client_id'),item.get('entry_fill'),
                             item.get('entry_filled_at'),item.get('exit_due_date'),item.get('exit_order_id'),
                             item.get('exit_client_id'),item.get('exit_fill'),item.get('exit_filled_at'),'CLOSED',
                             item.get('pnl'),'recovered closed round trip from Alpaca',item.get('horizon'),
                             item.get('window'),'BROKER_REPAIR'))
                inserted+=1
        con.commit()
    except Exception:
        con.rollback(); raise
    finally:
        con.close()
    mem_set('ui:dash',None)
    return {'updated':updated,'inserted':inserted}

def _close_trade_from_broker_exit(tr, order):
    fp=float(order.get('filled_avg_price') or 0)
    ft=order.get('filled_at')
    pnl=(fp-float(tr.get('entry_fill') or 0))*100*int(tr.get('qty') or 1)
    con=db(); con.execute("""UPDATE trades SET exit_order_id=?,exit_client_id=?,exit_fill=?,exit_filled_at=?,
                             status='CLOSED',pnl=?,exit_kind=COALESCE(NULLIF(exit_kind,''),'BROKER'),
                             broker_note=? WHERE id=?""",
                          (order.get('id'),order.get('client_order_id'),fp,ft,pnl,
                           'closed from broker sell on startup',tr['id']))
    con.commit(); con.close()
    event(f"CLOSED {tr['strategy_id']} {tr['ticker']} P&L ${pnl:.2f} (startup broker sell)")

def startup_reconcile():
    """Alpaca verifies live holdings. Activity (local trades) stays the book.

    Filled buys are recovered only when the broker still holds the contract.
    Closed history is never rebuilt from buy-side order replay.
    """
    init_db()
    c=cfg()
    if not (c.get('alpaca_key') and c.get('alpaca_secret')):
        if broker_orders_enabled():
            raise RuntimeError('broker orders enabled but Alpaca paper credentials are missing')
        event(f'Startup reconciliation skipped ({ENVIRONMENT}: no Alpaca credentials; broker orders disabled)')
        meta_set('startup_reconciled_at',now_ny().isoformat())
        return True
    reconcile()
    after=(now_ny()-timedelta(days=14)).astimezone(ZoneInfo('UTC')).isoformat()
    orders=getj(paper_api_url('/orders'),ah(),{'status':'all','after':after,'direction':'desc','limit':500},timeout=15)
    if not isinstance(orders,list):
        raise RuntimeError('Alpaca orders reconciliation returned an invalid payload')
    positions=getj(paper_api_url('/positions'),ah(),timeout=15)
    if not isinstance(positions,list):
        raise RuntimeError('Alpaca positions reconciliation returned an invalid payload')
    held=_broker_symbols(positions)
    recovered=0
    skipped_flat=0
    for order in orders:
        cid=order.get('client_order_id')
        parsed=_client_order_parts(cid)
        if not parsed or order.get('side')!='buy':continue
        con=db(); known=con.execute('SELECT id FROM trades WHERE entry_order_id=? OR entry_client_id=? LIMIT 1',(order.get('id'),cid)).fetchone(); con.close()
        if known:continue
        broker_status=str(order.get('status') or '')
        symbol=order.get('symbol')
        if broker_status in ('canceled','expired','rejected'):
            continue
        if broker_status=='filled':
            if symbol not in held:
                skipped_flat+=1
                continue
            status='OPEN'
        else:
            status='ENTRY_SUBMITTED'
        day,sid,ticker=parsed
        submitted=parse_ny(order.get('submitted_at') or order.get('created_at')) or now_ny()
        trade_date=(datetime.strptime(day,'%Y%m%d').date().isoformat() if day else submitted.date().isoformat())
        direction,expiry=_option_direction_expiry(symbol)
        horizon='EOD' if sid in MIDDAY_STRATEGY_IDS else 'OVERNIGHT'
        exit_due=trade_date if horizon=='EOD' else next_trading_date(trade_date)
        con=db(); con.execute('''INSERT INTO trades(strategy_id,ticker,direction,option_symbol,qty,signal_ts,trade_date,expiry,
                                 entry_order_id,entry_client_id,entry_fill,entry_filled_at,exit_due_date,status,broker_note,horizon,window)
                                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (sid,ticker,direction,symbol,int(float(order.get('qty') or 0)),submitted.isoformat(),trade_date,expiry,
                               order.get('id'),cid,float(order.get('filled_avg_price') or 0) or None,order.get('filled_at'),exit_due,status,
                               'recovered by startup reconciliation',horizon,sid if horizon=='EOD' else '15:45'))
        con.commit(); con.close(); recovered+=1
        event(f'Recovered broker order {cid} into the local trade ledger','WARN')
    expire_dead_options()
    today=now_ny().date().isoformat()
    con=db(); local_open=[dict(x) for x in con.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()]; con.close()
    missing=[]
    for tr in local_open:
        if tr.get('option_symbol') in held:
            continue
        sell=_matching_exit_fill(tr, orders)
        if sell:
            _close_trade_from_broker_exit(tr, sell)
            continue
        due=(tr.get('exit_due_date') or '')[:10]
        eod_due_passed=(tr.get('horizon') or 'OVERNIGHT')=='EOD' and due and due<today
        if _option_is_worthless(tr) or eod_due_passed:
            _expire_trade(tr, 'broker flat after Activity still OPEN')
            continue
        missing.append(str(tr['id']))
    if missing:
        event('Startup reconciliation: local OPEN trades absent from Alpaca positions: '+','.join(missing),'ERROR')
        raise RuntimeError('startup reconciliation found missing broker positions for local trades: '+','.join(missing))
    meta_set('startup_reconciled_at',now_ny().isoformat())
    meta_set('startup_recovered_orders',recovered)
    meta_set('startup_skipped_flat_buys',skipped_flat)
    event(f'Startup reconciliation complete: {len(orders)} orders checked, {recovered} recovered, {skipped_flat} filled buys ignored (broker already flat)')
    return True

def expire_dead_options():
    """0DTE still OPEN after the close is worthless — do not keep sending market sells."""
    con=db(); rows=[dict(x) for x in con.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()]; con.close()
    for tr in rows:
        if _option_is_worthless(tr):
            _expire_trade(tr)

def submit_due_exits():
    expire_dead_options()
    n=now_ny(); hm=n.strftime('%H:%M')
    if n.weekday()>=5 or hm>='16:00' or hm<'09:30':
        return
    con=db(); rows=con.execute("SELECT * FROM trades WHERE status='OPEN' AND exit_due_date<=?",(n.date().isoformat(),)).fetchall(); con.close()
    for tr in rows:
        tr=dict(tr)
        if meta_get(f"exit_skip_{tr['id']}_{n.date().isoformat()}")=='1':
            continue
        horizon=(tr.get('horizon') or 'OVERNIGHT')
        if horizon=='EOD':
            if hm<'15:50':continue
        elif hm<'09:35':
            continue
        try:
            submit_exit(tr, 'SCHEDULE')
        except Exception as e:
            msg=str(e)
            meta_set(f"exit_skip_{tr['id']}_{n.date().isoformat()}",'1')
            con=db(); con.execute('UPDATE trades SET broker_note=? WHERE id=?',(msg[:240],tr['id'])); con.commit(); con.close()
            if meta_get(f"exit_err_{tr['id']}")!='1':
                event(f"Exit error trade {tr['id']}: {e}",'ERROR')
                meta_set(f"exit_err_{tr['id']}",'1')

def evaluate_and_trade(force_preview=False):
    states=build_market_state(); signals,context=strategy_signals(states)
    journal_snapshot(states,signals,'15:45')
    if force_preview:return {'signals':signals,'context':context,'states':{k:{x:v for x,v in s.items() if x not in ('daily','closes')} for k,s in states.items()}}
    date=now_ny().date().isoformat()
    if meta_get('evaluated_'+date)=='1':return {'note':'already evaluated'}
    con=db()
    for s in signals:con.execute('INSERT INTO signals(ts,trade_date,strategy_id,ticker,direction,score,details,execution_status,window,horizon) VALUES(?,?,?,?,?,?,?,?,?,?)',(now_ny().isoformat(),date,s['strategy_id'],s['ticker'],s['direction'],s['score'],json.dumps(s['details']),'PENDING',s.get('window','15:45'),s.get('horizon','OVERNIGHT')))
    con.commit(); con.close()
    for s in rank_signals(signals):
        try:
            status,extra=submit_entry(s,states); con=db(); con.execute('''UPDATE signals SET execution_status=?,note=? WHERE id=(SELECT id FROM signals WHERE trade_date=? AND strategy_id=? AND ticker=? ORDER BY id DESC LIMIT 1)''',(status,json.dumps(extra or {}),date,s['strategy_id'],s['ticker'])); con.commit(); con.close(); event(f"{s['strategy_id']} {s['ticker']} {s['direction']} -> {status}")
        except Exception as e:event(f"{s['strategy_id']} {s['ticker']} entry error: {e}",'ERROR')
    meta_set('evaluated_'+date,'1'); meta_set('last_eval',now_ny().isoformat()); return {'signals':signals,'context':context}

def evaluate_midday(which='BOTH', force_preview=False):
    date=now_ny().date().isoformat()
    try: ingest_live_data(force=force_preview)
    except Exception as e: event(f'Midday ingest: {e}','WARN')
    states={}
    for sym in MIDDAY_TICKERS:
        st=local_intraday_state(sym,date)
        if st: states[sym]=st
    if not states:
        return {'note':'no local live bars yet','signals':[],'states':{}}
    lasts=[]
    for st in states.values():
        dt=parse_ny(st.get('last_bar'))
        if dt: lasts.append(dt)
    if lasts:
        freshest=max(lasts)
        for st in states.values():
            dt=parse_ny(st.get('last_bar'))
            if dt and (freshest-dt).total_seconds()>120: st['halt']=True
    signals,evals,context=midday_signals(states,which,ignore_clock=force_preview)
    snap_window=which if which in MIDDAY_STRATEGY_IDS else 'LIVE'
    if not force_preview: journal_midday(states,evals,snap_window)
    compact={k:compact_state(v) for k,v in states.items()}
    if force_preview: return {'signals':signals,'evals':evals,'context':context,'states':compact}
    fired=[]
    for s in rank_signals(signals):
        if already_signaled(date,s['strategy_id'],s['ticker']): continue
        con=db(); con.execute('INSERT INTO signals(ts,trade_date,strategy_id,ticker,direction,score,details,execution_status,window,horizon) VALUES(?,?,?,?,?,?,?,?,?,?)',
                              (now_ny().isoformat(),date,s['strategy_id'],s['ticker'],s['direction'],s['score'],json.dumps(s.get('details') or {},default=str),'PENDING',s.get('window'),s.get('horizon','EOD'))); con.commit(); con.close()
        try:
            status,extra=submit_entry(s,states); con=db(); con.execute('''UPDATE signals SET execution_status=?,note=? WHERE id=(SELECT id FROM signals WHERE trade_date=? AND strategy_id=? AND ticker=? ORDER BY id DESC LIMIT 1)''',(status,json.dumps(extra or {},default=str),date,s['strategy_id'],s['ticker'])); con.commit(); con.close()
            event(f"{s['strategy_id']} {s['ticker']} {s['direction']} {s.get('window')} -> {status}")
            fired.append({**s,'execution_status':status})
        except Exception as e:
            con=db(); con.execute('''UPDATE signals SET execution_status=?,note=? WHERE id=(SELECT id FROM signals WHERE trade_date=? AND strategy_id=? AND ticker=? ORDER BY id DESC LIMIT 1)''',
                                  ('ERROR',str(e)[:400],date,s['strategy_id'],s['ticker'])); con.commit(); con.close()
            event(f"{s['strategy_id']} {s['ticker']} midday entry error: {e}",'ERROR')
    if fired: meta_set('last_midday_eval',now_ny().isoformat())
    elif evals: meta_set('last_midday_scan',now_ny().isoformat())
    return {'signals':fired,'scanned':len(states),'window':context.get('clock'),'context':context}

def maybe_notify(text):
    try:
        if shutil.which('termux-notification'):subprocess.run(['termux-notification','--title','ASH Terminal','--content',text],timeout=5)
    except:pass
    url=(cfg().get('ntfy_url') or '').strip()
    if url:
        try:
            requests.post(url, data=text.encode(), headers={'Title':'ASH Terminal'}, timeout=6)
        except Exception: pass

def runner_loop(heartbeat_callback=None):
    event('Persistent paper runner started')
    while True:
        try:
            n=now_ny(); hm=n.strftime('%H:%M'); date=n.date().isoformat()
            meta_set('heartbeat',n.isoformat()); meta_set('runner_pid',str(os.getpid()))
            if heartbeat_callback: heartbeat_callback(n)
            if not keys_ok():
                time.sleep(30); continue
            try: maybe_snapshot_account()
            except Exception as e: event(f'Account snapshot: {e}','WARN')
            reconcile(); submit_due_exits()
            try: refresh_excursions_and_stops()
            except Exception as e: event(f'Manage open: {e}','WARN')
            if n.weekday()<5 and '09:25'<=hm<='16:10':
                try: ingest_live_data()
                except Exception as e: event(f'Live ingest: {e}','WARN')
                try: ensure_daily_cache()
                except Exception as e: event(f'Daily cache retry: {e}','WARN')
                if hm<'09:35' or hm>='16:05':
                    if meta_get('minute_hist_'+date)!='1':
                        try: ensure_minute_history()
                        except Exception as e: event(f'Minute history: {e}','WARN')
                else:
                    kick_minute_history()
            elif n.weekday()<5 and hm<'09:35':
                try: ensure_daily_cache()
                except Exception as e: event(f'Daily cache retry: {e}','WARN')
                if meta_get('minute_hist_'+date)!='1':
                    try: ensure_minute_history()
                    except Exception as e: event(f'Minute history: {e}','WARN')
            if n.weekday()<5 and '09:35'<=hm<='14:30':
                res=evaluate_midday('ALL')
                fired=res.get('signals') or []
                by={}
                for s in fired: by[s.get('strategy_id')]=by.get(s.get('strategy_id'),0)+1
                for sid,nfire in by.items():
                    notify_once(f'notif_{date}_{sid}', f"{nfire} {sid} signal(s). Open local dashboard.")
            if n.weekday()<5 and '15:45'<=hm<='15:49':
                before=meta_get('evaluated_'+date); res=evaluate_and_trade(False)
                if before!='1' and res.get('signals'): notify_once(f'notif_{date}_EOD', f"{len(res['signals'])} 3:45 strategy signal(s) fired. Open local dashboard.")
            if n.weekday()<5 and '16:05'<=hm<='16:20' and meta_get('debrief_nudge_'+date)!='1':
                notify_once(f'debrief_nudge_{date}', 'Session closed. Three debrief questions are waiting in Lab.')
                meta_set('debrief_nudge_'+date,'1')
        except Exception as e:
            event('Runner cycle error: '+str(e)+'\n'+traceback.format_exc()[-1000:],'ERROR')
        time.sleep(30)

INTRO_TARGET=DATA/'intro_target.json'
INTRO_NAME_RE=re.compile(r'^intro-[a-z0-9-]+\.webm$')
INTRO_MAX=32_000_000
app.config['MAX_CONTENT_LENGTH']=INTRO_MAX
_intro_save_lock=threading.Lock()

@app.errorhandler(413)
def _too_large(_e):
    return jsonify({'error':'too large'}),413

@app.get('/')
def home():return send_from_directory(STATIC,'index.html')
@app.get('/api/intro-target')
def intro_target_get():
    if INTRO_TARGET.exists():
        try: return jsonify(json.loads(INTRO_TARGET.read_text()))
        except Exception: pass
    return jsonify({'w':390,'h':844,'dpr':2})
@app.post('/api/intro-target')
def intro_target_post():
    d=request.get_json(silent=True) or {}
    try:
        w=int(d.get('w') or 0); h=int(d.get('h') or 0); dpr=float(d.get('dpr') or 1)
    except (TypeError,ValueError):
        return jsonify({'error':'bad size'}),400
    if not (200<=w<=2000 and 400<=h<=4000):
        return jsonify({'error':'bad size'}),400
    payload={'w':w,'h':h,'dpr':min(max(dpr,1),3)}
    if d.get('cssW') is not None: payload['cssW']=d.get('cssW')
    if d.get('cssH') is not None: payload['cssH']=d.get('cssH')
    INTRO_TARGET.write_text(json.dumps(payload))
    return jsonify({'ok':True,**payload})
@app.post('/api/intro-save')
def intro_save():
    name=(request.args.get('name') or '').strip()
    if not INTRO_NAME_RE.match(name):
        return jsonify({'error':'bad name'}),400
    path=(STATIC/name).resolve()
    if path.parent!=STATIC.resolve() or path.suffix!='.webm':
        return jsonify({'error':'bad name'}),400
    tmp=path.with_name(path.name+'.part')
    with _intro_save_lock:
        n=0
        try:
            with open(tmp,'wb') as f:
                while True:
                    chunk=request.stream.read(64*1024)
                    if not chunk: break
                    n+=len(chunk)
                    if n>INTRO_MAX:
                        raise ValueError('too large')
                    f.write(chunk)
            if n<1000:
                tmp.unlink(missing_ok=True)
                return jsonify({'error':'empty or too large'}),400
            os.replace(tmp, path)
        except ValueError:
            try: tmp.unlink(missing_ok=True)
            except Exception: pass
            return jsonify({'error':'too large'}),413
        except Exception:
            try: tmp.unlink(missing_ok=True)
            except Exception: pass
            raise
    return jsonify({'ok':True,'file':name,'bytes':n})

@app.before_request
def _guest_lan():
    if request.method in ('GET','HEAD','OPTIONS'): return
    if not request.path.startswith('/api/'): return
    if orders_allowed(): return
    return jsonify({'error':'guest LAN is read-only; paper orders stay on this device','guest':True}),403
@app.get('/manifest.webmanifest')
def manifest():return send_from_directory(STATIC,'manifest.webmanifest')
@app.get('/sw.js')
def sw():return send_from_directory(STATIC,'sw.js')
@app.get('/api/status')
def status():
    return jsonify(status_payload())

def status_payload():
    c=cfg()
    rh=runner_health()
    con=db()
    bars=con.execute("SELECT COUNT(*) n FROM live_bars").fetchone()['n']
    calls=con.execute("SELECT COUNT(*) n FROM api_log").fetchone()['n'] if con.execute("SELECT name FROM sqlite_master WHERE name='api_log'").fetchone() else 0
    rate=con.execute("SELECT COUNT(*) n FROM api_log WHERE ts>=?",((now_ny()-timedelta(seconds=60)).isoformat(),)).fetchone()['n'] if calls else 0
    unread=con.execute("SELECT COUNT(*) n FROM events WHERE IFNULL(seen,0)=0 AND level IN ('WARN','ERROR')").fetchone()['n']
    con.close()
    cov_pct=meta_get('session_coverage_pct'); ing=meta_get('last_ingest'); stale=None
    if ing:
        try: stale=(now_ny()-datetime.fromisoformat(ing)).total_seconds()
        except Exception: stale=None
    snap=stored_account()
    return {
        'configured':keys_ok(),
        'paper_only':True,'broker_orders_enabled':broker_orders_enabled(),
        'broker_config_enabled':c.get('broker_orders_enabled') is True,
        'broker_runtime_armed':broker_runtime_armed(),
        'environment':ENVIRONMENT,
        'release':ROOT.name,
        'runner_release':meta_get('runner_release'),
        'heartbeat':meta_get('heartbeat'),'last_eval':meta_get('last_eval'),
        'last_ingest':ing,'last_ingest_source':meta_get('last_ingest_source'),
        'last_midday_eval':meta_get('last_midday_eval'),'last_midday_scan':meta_get('last_midday_scan'),
        'live_tickers':MIDDAY_TICKERS,'time_ny':now_ny().isoformat(),
        'session_complete_pct':float(cov_pct) if cov_pct not in (None,'') else None,
        'clock':session_clock(),'stale_sec':stale,'data_stale':bool(stale is not None and stale>90),
        'watchdog_stale':not rh['ok'],
        'heartbeat_age':rh['runner_heartbeat_age_sec'],
        'guest':not orders_allowed(),
        'wake_lock':bool(shutil.which('termux-wake-lock')),
        'rate_budget':{'calls_60s':rate,'ok':rate<80},
        'unread_errors':unread,
        'thresholds':thresh(),
        'account_snapshot_at':snap.get('snapshot_at') or snap.get('ts'),
        'cache':{'hits':_API_STATS['hits'],'misses':_API_STATS['misses'],'http_calls':_API_STATS['calls'],
                 'hit_rate':(_API_STATS['hits']/max(1,_API_STATS['hits']+_API_STATS['misses'])),
                 'local_bars':bars,'api_log_rows':calls}
    }

def runner_health(max_age=90):
    hb=meta_get('heartbeat'); age=None
    if hb:
        dt=parse_ny(hb)
        if dt: age=max(0.0,(now_ny()-dt).total_seconds())
    healthy=bool(age is not None and age<=max_age)
    return {'ok':healthy,'runner_heartbeat':hb,'runner_heartbeat_age_sec':age,
            'max_age_sec':max_age,'environment':ENVIRONMENT,'web_pid':os.getpid()}

@app.get('/api/health')
def health():
    payload=runner_health()
    return jsonify(payload),(200 if payload['ok'] else 503)
@app.post('/api/config')
def setconfig():
    d=request.get_json(force=True) or {}; c=cfg()
    for k in ('alpaca_key','alpaca_secret','fred_key','fomc_dates','ntfy_url','earnings_dates'):
        if k in d:c[k]=d[k]
    if 'allow_lan_orders' in d: c['allow_lan_orders']=bool(d['allow_lan_orders'])
    c['broker_orders_enabled']=bool(d.get('broker_orders_enabled', c.get('broker_orders_enabled',False))); c['contracts_per_trade']=max(1,min(5,int(d.get('contracts_per_trade',c.get('contracts_per_trade',1)))));
    if any(k in d for k in ('alpaca_key','alpaca_secret','fred_key')):
        c['keys_ok']=False
    save_cfg(c); return jsonify({'ok':True})
@app.post('/api/test')
def test():
    out={'alpaca':False,'fred':False,'paper_account':False,'errors':[]}
    try:out['alpaca']=bool(getj(f'{MD}/v2/stocks/SPY/snapshot',ah(),{'feed':'iex'}))
    except Exception as e:out['errors'].append('Alpaca data: '+str(e))
    try:out['paper_account']=bool(getj(paper_api_url('/account'),ah()))
    except Exception as e:out['errors'].append('Paper account: '+str(e))
    try:out['fred']=latest_vix()[1] is not None
    except Exception as e:out['errors'].append('FRED: '+str(e))
    c=cfg(); c['keys_ok']=bool(out['alpaca'] and out['paper_account'] and out['fred']); save_cfg(c)
    out['ok']=c['keys_ok']
    return jsonify(out)

def broker_account():
    a=getj_cached(paper_api_url('/account'),ah(),ttl=20,key='broker:account')
    return {k:a.get(k) for k in ("id","status","currency","cash","portfolio_value","equity",
                                 "last_equity","buying_power","options_buying_power","daytrade_count",
                                 "pattern_day_trader","trading_blocked")}

def broker_positions():
    p=getj_cached(paper_api_url('/positions'),ah(),ttl=15,key='broker:positions') or []
    return p if isinstance(p,list) else []

@app.get('/api/account')
def account():
    try: return jsonify(live_or_stored_account())
    except Exception as e: return jsonify({"error":str(e)}),500

@app.get('/api/positions')
def positions():
    try:
        rows=[]
        for x in broker_positions():
            rows.append({k:x.get(k) for k in ("symbol","qty","side","market_value","cost_basis",
                                              "unrealized_pl","unrealized_plpc","current_price",
                                              "avg_entry_price","change_today")})
        return jsonify({"positions":rows})
    except Exception as e:
        return jsonify({"positions":[],"error":str(e)})

@app.get('/api/market_chart/<sym>')
def market_chart(sym):
    sym=sym.upper()
    if sym not in ALL_TICKERS:return jsonify({"error":"unsupported ticker"}),400
    days=max(20,min(365,int(request.args.get("days","90"))))
    ensure_daily_cache([sym],days)
    try:
        bars=load_local_bars_since(sym,'1Day',(now_ny().date()-timedelta(days=days*2)).isoformat())
        if len(bars)<days:
            end=now_ny(); start=end-timedelta(days=days*2)
            fetched=fetch_bars(sym,start.isoformat(),end.isoformat(),"1Day","iex")
            upsert_live_bars(sym,'1Day',fetched)
            bars=load_local_bars_since(sym,'1Day',(now_ny().date()-timedelta(days=days*2)).isoformat())
        bars=bars[-days:]
        closes=[float(b["c"]) for b in bars]
        e20=ema_series(closes,20) if closes else []
        out=[]
        for i,b in enumerate(bars):
            sub=closes[max(0,i-19):i+1]
            mid=avg(sub) if len(sub)>=20 else None
            sig=statistics.stdev(sub) if len(sub)>=20 else None
            out.append({
                "t":(b.get("trade_date") or str(b["t"])[:10]),"o":float(b["o"]),"h":float(b["h"]),"l":float(b["l"]),"c":float(b["c"]),
                "v":float(b["v"]),"ema20":e20[i] if i<len(e20) else None,
                "bbUpper":(mid+2*sig) if sig is not None else None,
                "bbLower":(mid-2*sig) if sig is not None else None,
            })
        return jsonify({"ticker":sym,"bars":out,"source":"local-sqlite"})
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.get('/api/dashboard')
def dashboard():
    return jsonify(dashboard_payload())

def dashboard_payload():
    hit=mem_get('ui:dash',12)
    if hit is not None: return hit
    con=db()
    trades=[dict(x) for x in con.execute("SELECT * FROM trades ORDER BY id ASC").fetchall()]
    sigs=[dict(x) for x in con.execute("SELECT * FROM signals ORDER BY id ASC").fetchall()]
    ev=[dict(x) for x in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 25").fetchall()]
    con.close()

    # Strategy aggregates + paper equity curve from realized P&L.
    strat={}
    for s in STRATEGIES:
        rows=[t for t in trades if t.get("strategy_id")==s["id"] and t.get("status")=="CLOSED" and t.get("pnl") is not None]
        pnls=[float(t.get("pnl") or 0) for t in rows]
        wins=sum(1 for p in pnls if p>0)
        strat[s["id"]]={
            "id":s["id"],"name":s["name"],"origin":s["origin"],"author":s["author"],"desc":s["desc"],
            "plain":s.get("plain"),"session":s.get("session"),"horizon":s.get("horizon"),"opt":s.get("opt"),
            "signals":sum(1 for x in sigs if x.get("strategy_id")==s["id"]),
            "closed":len(rows),"wins":wins,"winRate":wins/len(rows) if rows else None,
            "pnl":sum(pnls),"avgPnl":avg(pnls) if pnls else None
        }
    rm=compute_research_metrics()
    by={x['id']:x for x in rm.get('strategies') or []}
    for sid,row in strat.items():
        extra=by.get(sid) or {}
        row.update({k:extra.get(k) for k in ('opportunities','fires','misses','fireRate','winLo','winHi','expectancy','profitFactor','sample','nDays')})

    closed=[t for t in trades if t.get("status")=="CLOSED" and t.get("pnl") is not None]
    closed.sort(key=realized_sort_key)
    curve=[];cum=0.0
    daily={}
    for t in closed:
        pnl=float(t.get("pnl") or 0);cum+=pnl
        dt=realized_date(t)
        curve.append({"date":dt,"pnl":pnl,"cumPnl":cum,"strategy":t.get("strategy_id"),"ticker":t.get("ticker")})
        daily[dt]=daily.get(dt,0)+pnl

    ticker_stats={}
    names=list(dict.fromkeys(ALL_TICKERS+[t.get("ticker") for t in trades if t.get("ticker")]))
    for tk in names:
        rr=[t for t in closed if t.get("ticker")==tk]
        pp=[float(t.get("pnl") or 0) for t in rr]
        ticker_stats[tk]={"closed":len(rr),"pnl":sum(pp),"wins":sum(1 for p in pp if p>0),
                          "winRate":sum(1 for p in pp if p>0)/len(pp) if pp else None}

    today=now_ny().date().isoformat()
    closed_today=[t for t in closed if realized_date(t)==today]
    realized_today=sum(float(t.get('pnl') or 0) for t in closed_today)
    payload={
        "strategies":list(strat.values()),
        "curve":curve,
        "dailyPnl":[{"date":k,"pnl":v} for k,v in sorted(daily.items())],
        "tickerStats":ticker_stats,
        "openTrades":[t for t in trades if t.get("status") in OPEN_TRADE_STATUSES],
        "recentEvents":ev,
        "totals":{
            "signals":len(sigs),"trades":len(trades),"closed":len(closed),
            "open":sum(1 for t in trades if t.get("status") in OPEN_TRADE_STATUSES),
            "wins":sum(1 for t in closed if float(t.get("pnl") or 0)>0),
            "realizedPnl":sum(float(t.get("pnl") or 0) for t in closed),
            "realizedToday":realized_today,
            "sessionDate":today,
        }
    }
    mem_set('ui:dash',payload)
    return payload


def _historical_state(sym,date,cutoff="15:45"):
    target=datetime.strptime(date,"%Y-%m-%d").replace(tzinfo=NY)
    start=(target.date()-timedelta(days=330)).isoformat()+"T00:00:00Z"
    end=(target.date()+timedelta(days=1)).isoformat()+"T00:00:00Z"
    daily=fetch_bars(sym,start,end,"1Day","sip")
    if not daily:
        daily=fetch_bars(sym,start,end,"1Day","iex")
    completed=[b for b in daily if b["t"][:10]<date]
    mins=fetch_bars(sym,date+"T00:00:00Z",end,"1Min","sip")
    session=[]
    for b in mins:
        dt=datetime.fromisoformat(b["t"].replace("Z","+00:00")).astimezone(NY)
        if dt.date().isoformat()==date and "09:30"<=dt.strftime("%H:%M")<=cutoff:
            session.append(b)
    if not session or len(completed)<210:
        raise RuntimeError(f"{sym} {date}: insufficient replay data")
    session.sort(key=lambda x:x["t"])
    o=float(session[0]["o"]); h=max(float(x["h"]) for x in session); l=min(float(x["l"]) for x in session); c=float(session[-1]["c"])
    vol=sum(float(x.get("v",0) or 0) for x in session)
    closes=[float(b["c"]) for b in completed]+[c]
    return {"sym":sym,"date":date,"o":o,"h":h,"l":l,"c":c,"vol":vol,"session":session,"daily":completed,
            "closes":closes,"highs":[float(b["h"]) for b in completed],"lows":[float(b["l"]) for b in completed],
            "rsi3":rsi_simple(closes,3),"rsi2":rsi_simple(closes,2),
            "cp":(c-l)/(h-l) if h>l else .5,"ret":c/float(completed[-1]["c"])-1,
            "ret45":0.0,"rvol":None,"feed":"sip-replay"}

def _historical_signals_at_1545(date):
    states={}
    # Pull a 45-day SIP minute window for apples-to-apples 15:45 volume baseline.
    for sym in TICKERS:
        s=_historical_state(sym,date,"15:45")
        tgt=datetime.strptime(date,"%Y-%m-%d").date()
        wstart=(tgt-timedelta(days=45)).isoformat()+"T00:00:00Z"
        wend=(tgt+timedelta(days=1)).isoformat()+"T00:00:00Z"
        mins=fetch_bars(sym,wstart,wend,"1Min","sip")
        sessions={}
        for b in mins:
            dt=datetime.fromisoformat(b["t"].replace("Z","+00:00")).astimezone(NY)
            hm=dt.strftime("%H:%M"); d=dt.date().isoformat()
            if dt.weekday()<5 and "09:30"<=hm<="15:45":
                sessions.setdefault(d,[]).append(b)
        prior=sorted(d for d in sessions if d<date)[-20:]
        if len(prior)==20:
            base=avg([sum(float(x.get("v",0) or 0) for x in sessions[d]) for d in prior])
            s["rvol"]=s["vol"]/base if base else None
        # 45m return
        ss=s["session"]
        late=[b for b in ss if datetime.fromisoformat(b["t"].replace("Z","+00:00")).astimezone(NY).strftime("%H:%M")>="15:00"]
        s["ret45"]=s["c"]/float(late[0]["o"])-1 if late else 0
        states[sym]=s

    # Historical VIX/macros are used only for CEG gating.
    try:
        j=fredj("/series/observations",{"series_id":"VIXCLS","observation_start":date,"observation_end":date})
        vx=next((float(x["value"]) for x in j.get("observations",[]) if x.get("value") not in (".",None)),None)
    except: vx=None
    tomorrow=next_trading_date(date)
    macros=macro_dates(date,(datetime.strptime(date,"%Y-%m-%d").date()+timedelta(days=10)).isoformat())
    macro_clear=tomorrow not in macros

    out=[]
    def add(sid,ticker,direction,score,details):
        out.append({"strategy_id":sid,"ticker":ticker,"direction":direction,"score":float(score),"details":details})

    for sym,s in states.items():
        c=s["c"]; closes=s["closes"]; daily=s["daily"]; cp=s["cp"]; rv=s["rvol"] or 0
        if s["rsi3"] is not None and s["rsi3"]<15 and cp<.30 and rv>1.2 and vx is not None and vx>=15 and macro_clear:
            add("CEG",sym,"CALL",1,{"rsi3":s["rsi3"],"cp":cp,"rvol":rv,"vix":vx})
        body=abs(c-s["o"]); lower=min(s["o"],c)-s["l"]
        if c>s["o"] and lower>1.5*max(body,.01) and rv>1.2:
            add("VCT",sym,"CALL",lower/max(body,.01),{"lower_shadow":lower,"body":body,"rvol":rv})
        others=[x for k,x in states.items() if k!=sym]
        div=avg([x["ret"] for x in others])-s["ret"]
        if s["rsi3"] is not None and s["rsi3"]<20 and cp<.25 and rv>1.2 and div>.0075:
            add("XED",sym,"CALL",div*100,{"divergence_pp":div*100})
        prev5=min(float(x["l"]) for x in daily[-5:])
        if s["l"]<prev5 and cp>.70 and s["ret45"]>.005 and rv>1.2:
            add("LAR",sym,"CALL",s["ret45"]*100,{"cp":cp,"ret45":s["ret45"],"rvol":rv})
        ma200=sma(closes[:-1],200)
        if ma200 and c>ma200 and s["rsi2"] is not None and s["rsi2"]<10:
            add("RSI2",sym,"CALL",(10-s["rsi2"])/10,{"rsi2":s["rsi2"]})
        prev20=closes[-21:-1]
        if len(prev20)==20:
            mid=avg(prev20); sig=sd(prev20)
            if sig:
                if c<mid-2*sig:add("BB",sym,"CALL",(mid-2*sig-c)/sig,{"mid":mid})
                elif c>mid+2*sig:add("BB",sym,"PUT",(c-mid-2*sig)/sig,{"mid":mid})
        if len(closes)>=40:
            e12=ema_series(closes,12);e26=ema_series(closes,26);m=[a-b for a,b in zip(e12,e26)];sg=ema_series(m,9)
            if m[-2]<=sg[-2] and m[-1]>sg[-1]:add("MACD",sym,"CALL",m[-1]-sg[-1],{})
            elif m[-2]>=sg[-2] and m[-1]<sg[-1]:add("MACD",sym,"PUT",sg[-1]-m[-1],{})
        hi20=max(float(x["h"]) for x in daily[-20:]);lo20=min(float(x["l"]) for x in daily[-20:])
        if c>hi20:add("DON",sym,"CALL",(c/hi20-1)*100,{})
        elif c<lo20:add("DON",sym,"PUT",(lo20/c-1)*100,{})
        kp,dp,kn,dn=stochastic(s)
        if None not in (kp,dp,kn,dn):
            if kp<=dp and kn>dn and kn<25:add("STO",sym,"CALL",(25-kn)/25,{})
            elif kp>=dp and kn<dn and kn>75:add("STO",sym,"PUT",(kn-75)/25,{})
        at=atr(daily[-30:]+[{"h":s["h"],"l":s["l"],"c":c}],20)
        if len(closes)>=25 and at:
            em=ema_series(closes,20)[-1]
            if c>em+2*at:add("KEL",sym,"CALL",(c-em-2*at)/at,{})
            elif c<em-2*at:add("KEL",sym,"PUT",(em-2*at-c)/at,{})
    return states,out,{"vix":vx,"macro_clear":macro_clear}

@app.get('/api/replay/<sym>')
def replay(sym):
    sym=sym.upper(); date=request.args.get("date")
    if sym not in TICKERS or not date:return jsonify({"error":"ticker/date required"}),400
    try:
        states,sigs,ctx=_historical_signals_at_1545(date)
        state=states[sym]
        bars=[]
        for b in state["session"]:
            dt=datetime.fromisoformat(b["t"].replace("Z","+00:00")).astimezone(NY)
            bars.append({"t":dt.isoformat(),"o":float(b["o"]),"h":float(b["h"]),"l":float(b["l"]),"c":float(b["c"]),"v":float(b["v"])})
        # Directional replay outcome: underlying next-session open vs 3:45 signal price.
        # This is a directional proxy, NOT historical option P&L.
        sigs_for_ticker=[x for x in sigs if x["ticker"]==sym]
        next_open=None
        try:
            start=(datetime.strptime(date,"%Y-%m-%d").date()+timedelta(days=1)).isoformat()+"T00:00:00Z"
            end=(datetime.strptime(date,"%Y-%m-%d").date()+timedelta(days=8)).isoformat()+"T23:59:59Z"
            dbars=fetch_bars(sym,start,end,"1Day","sip")
            if not dbars:
                dbars=fetch_bars(sym,start,end,"1Day","iex")
            if dbars:
                next_open=float(sorted(dbars,key=lambda x:x["t"])[0]["o"])
        except Exception:
            next_open=None

        entry_price=float(state["c"])
        for s in sigs_for_ticker:
            direction=s.get("direction")
            worked=None
            ret=None
            if next_open is not None and entry_price:
                ret=next_open/entry_price-1
                if direction=="CALL":
                    worked=next_open>entry_price
                elif direction=="PUT":
                    worked=next_open<entry_price
            s["entryUnderlying"]=entry_price
            s["nextOpenUnderlying"]=next_open
            s["underlyingReturnToNextOpen"]=ret
            s["directionWorked"]=worked

        return jsonify({"ticker":sym,"date":date,"bars":bars,
                        "signals":sigs_for_ticker,
                        "allSignals":sigs,"context":ctx,
                        "entryUnderlying":entry_price,
                        "nextOpenUnderlying":next_open})
    except Exception as e:return jsonify({"error":str(e)}),500

@app.get('/api/signal_days')
def signal_days():
    con=db()
    rows=[dict(x) for x in con.execute("""SELECT trade_date,COUNT(*) signals,GROUP_CONCAT(strategy_id||':'||ticker) labels
                                          FROM signals GROUP BY trade_date ORDER BY trade_date DESC LIMIT 180""").fetchall()]
    snaps=[dict(x) for x in con.execute("""SELECT trade_date,COUNT(*) snapshots FROM snapshots GROUP BY trade_date ORDER BY trade_date DESC LIMIT 180""").fetchall()]
    con.close()
    by={x["trade_date"]:x for x in rows}
    for x in snaps:
        by.setdefault(x["trade_date"],{"trade_date":x["trade_date"],"signals":0,"labels":""})["snapshots"]=x["snapshots"]
    return jsonify({"days":sorted(by.values(),key=lambda x:x["trade_date"],reverse=True)})

@app.get('/api/near_misses')
def near_misses():
    con=db()
    rows=[dict(x) for x in con.execute("""SELECT trade_date,strategy_id,ticker,reason,ts FROM strategy_journal WHERE eligible=0
                                          UNION ALL
                                          SELECT trade_date,strategy_id,ticker,reason,ts FROM midday_evals WHERE eligible=0
                                          ORDER BY ts DESC LIMIT 300""").fetchall()]
    con.close()
    return jsonify({"rows":rows})

def compute_research_metrics(date=None):
    date=date or now_ny().date().isoformat()
    hit=mem_get('ui:rm:'+date,20)
    if hit is not None: return hit
    coverage=session_coverage(ALL_TICKERS, date)
    con=db()
    journals=[dict(x) for x in con.execute('SELECT trade_date,strategy_id,ticker,eligible,reason,metrics,ts FROM strategy_journal').fetchall()]
    midday=[dict(x) for x in con.execute('SELECT trade_date,strategy_id,ticker,eligible,reason,metrics,ts,window FROM midday_evals').fetchall()]
    trades=[dict(x) for x in con.execute('SELECT * FROM trades').fetchall()]
    con.close()
    rows=journals+midday
    by={s['id']:{'opportunities':0,'fires':0,'misses':0,'reasons':{}} for s in STRATEGIES}
    for r in rows:
        sid=r.get('strategy_id')
        if sid not in by: continue
        by[sid]['opportunities']+=1
        if r.get('eligible'): by[sid]['fires']+=1
        else:
            by[sid]['misses']+=1
            reason=normalize_reason(r.get('reason') or 'NO SIGNAL')
            by[sid]['reasons'][reason]=by[sid]['reasons'].get(reason,0)+1
    strategies=[]
    for s in STRATEGIES:
        st=by[s['id']]
        closed=[t for t in trades if t.get('strategy_id')==s['id'] and t.get('status')=='CLOSED' and t.get('pnl') is not None]
        pnls=[float(t.get('pnl') or 0) for t in closed]
        wins=sum(1 for p in pnls if p>0)
        gw=sum(p for p in pnls if p>0); gl=abs(sum(p for p in pnls if p<0))
        days=len({(t.get('trade_date') or '')[:10] for t in closed if t.get('trade_date')})
        lo,hi=wilson_interval(wins, len(pnls))
        opp=st['opportunities']
        strategies.append({
            'id':s['id'],'name':s['name'],'session':s.get('session'),'horizon':s.get('horizon'),
            'plain':s.get('plain'),'desc':s.get('desc'),
            'opportunities':opp,'fires':st['fires'],'misses':st['misses'],
            'fireRate':round(st['fires']/opp,4) if opp else None,
            'closed':len(pnls),'wins':wins,'nDays':days,
            'winRate':round(wins/len(pnls),4) if pnls else None,
            'winLo':lo,'winHi':hi,
            'pnl':round(sum(pnls),4),'expectancy':round(sum(pnls)/len(pnls),4) if pnls else None,
            'profitFactor':round(gw/gl,3) if gl else None,
            'sample':sample_label(days if days else len(pnls)),
            'reasons':sorted(st['reasons'].items(), key=lambda x:-x[1])[:8],
        })
    today_rows=[r for r in rows if r.get('trade_date')==date]
    today_reasons={}; today_by={}
    for r in today_rows:
        sid=r.get('strategy_id') or '?'
        today_by.setdefault(sid,{'fires':0,'misses':0,'opportunities':0})
        today_by[sid]['opportunities']+=1
        if r.get('eligible'): today_by[sid]['fires']+=1
        else:
            today_by[sid]['misses']+=1
            k=normalize_reason(r.get('reason') or 'NO SIGNAL')
            today_reasons[k]=today_reasons.get(k,0)+1
    edges=[i/4 for i in range(-12,13)]
    fire_h=[0]*(len(edges)-1); miss_h=[0]*(len(edges)-1)
    rsi_fire=[]; rsi_miss=[]
    for r in midday:
        if r.get('strategy_id')!='MVR': continue
        try: m=json.loads(r.get('metrics') or '{}')
        except Exception: m={}
        dist=m.get('vwap_dist_atr'); rsi=m.get('rsi5')
        if dist is None: continue
        idx=0
        if dist<edges[0]: idx=0
        elif dist>=edges[-1]: idx=len(edges)-2
        else:
            for i in range(len(edges)-1):
                if edges[i]<=dist<edges[i+1]: idx=i; break
        if r.get('eligible'): fire_h[idx]+=1
        else: miss_h[idx]+=1
        if rsi is not None: (rsi_fire if r.get('eligible') else rsi_miss).append(float(rsi))
    stretch_bins=[{'lo':edges[i],'hi':edges[i+1],'mid':round((edges[i]+edges[i+1])/2,3),
                   'fire':fire_h[i],'miss':miss_h[i]} for i in range(len(fire_h))]
    all_reasons={}
    for r in rows:
        if r.get('eligible'): continue
        k=normalize_reason(r.get('reason') or 'NO SIGNAL')
        all_reasons[k]=all_reasons.get(k,0)+1
    top_today=sorted(today_reasons.items(), key=lambda x:-x[1])
    fdr_src=[]
    for srow in strategies:
        n=srow.get('closed') or 0; w=srow.get('wins') or 0
        fdr_src.append({'id':srow['id'],'p':binom_p_two_sided(w,n) if n else 1.0,'n':n,'winRate':srow.get('winRate')})
    fdr=benjamini_hochberg(fdr_src,0.1)
    n_all=sum(s.get('closed') or 0 for s in strategies)
    days_all=max((s.get('nDays') or 0) for s in strategies) if strategies else 0
    mde=min_detectable_edge(days_all or n_all)
    loo=loo_fire_rates(rows)
    heat=seasonality_heatmap(midday)
    con=db(); shadows=[dict(x) for x in con.execute('SELECT status,skip_reason,strategy_id FROM shadow_trades ORDER BY id DESC LIMIT 400').fetchall()]; con.close()
    skip_tax={}
    for x in shadows:
        k=x.get('status') or 'SKIP'
        skip_tax[k]=skip_tax.get(k,0)+1
    out={
        'date':date,
        'clock':session_clock(),
        'coverage':coverage,
        'session_complete_pct':coverage_avg(coverage),
        'strategies':strategies,
        'today':{
            'fires':sum(1 for r in today_rows if r.get('eligible')),
            'misses':sum(1 for r in today_rows if not r.get('eligible')),
            'opportunities':len(today_rows),
            'by_strategy':today_by,
            'reasons':top_today[:8],
            'top_miss':top_today[0][0] if top_today else None,
        },
        'stretch_bins':stretch_bins,
        'mvr':{
            'rsi_fire_avg':round(sum(rsi_fire)/len(rsi_fire),2) if rsi_fire else None,
            'rsi_miss_avg':round(sum(rsi_miss)/len(rsi_miss),2) if rsi_miss else None,
            'n_fire':len(rsi_fire),'n_miss':len(rsi_miss),
        },
        'reasons':sorted(all_reasons.items(), key=lambda x:-x[1])[:12],
        'fdr':fdr,
        'mde':mde,'mde_n':days_all or n_all,
        'power_curve':power_curve(),
        'loo':loo,
        'seasonality':heat,
        'shadow':{'n':len(shadows),'by_status':sorted(skip_tax.items(), key=lambda x:-x[1])},
        'note':'Win-rate bands are Wilson 95% CIs. Sample uses unique days, not same-day fills. n<30 days is underpowered. MDE is the smallest win-rate edge vs 50% detectable at ~80% power.',
    }
    mem_set('ui:rm:'+date, out)
    return out

@app.get('/api/research_metrics')
def research_metrics():
    return jsonify(compute_research_metrics(request.args.get('date')))

@app.get('/api/overlap')
def overlap():
    con=db()
    rows=[dict(x) for x in con.execute("SELECT trade_date,strategy_id,ticker FROM signals").fetchall()]
    con.close()
    ids=[s["id"] for s in STRATEGIES]
    matrix={a:{b:0 for b in ids} for a in ids}
    grouped={}
    for r in rows: grouped.setdefault((r["trade_date"],r["ticker"]),set()).add(r["strategy_id"])
    for ss in grouped.values():
        for a in ss:
            for b in ss:
                matrix[a][b]+=1
    return jsonify({"ids":ids,"matrix":matrix})

@app.get('/api/model_drift')
def model_drift():
    # Historical reference currently available for CEG from canonical 3:45 research.
    # Other strategies remain "collecting" until enough forward samples exist.
    con=db()
    out=[]
    refs={"CEG":{"hist_win_rate":0.596,"hist_avg_underlying":0.005,"note":"Canonical 3:45 point-in-time reference"}}
    for st in STRATEGIES:
        rr=con.execute("""SELECT SUM(CASE WHEN status='CLOSED' AND pnl IS NOT NULL THEN 1 ELSE 0 END) n,
             SUM(CASE WHEN status='CLOSED' AND pnl IS NOT NULL AND pnl>0 THEN 1 ELSE 0 END) wins,
             AVG(CASE WHEN status='CLOSED' THEN pnl END) avgp
             FROM trades WHERE strategy_id=?""",(st["id"],)).fetchone()
        n=rr["n"] or 0
        ref=refs.get(st["id"])
        out.append({"id":st["id"],"n":n,"live_win_rate":(rr["wins"]/n if n else None),
                    "live_avg_pnl":rr["avgp"],**(ref or {})})
    con.close()
    return jsonify({"rows":out})

@app.get('/api/research_surface')
def research_surface():
    # Uses recorded snapshots to create an empirical CEG state-space cloud.
    con=db()
    snaps=[dict(x) for x in con.execute("SELECT trade_date,ticker,payload FROM snapshots ORDER BY id DESC LIMIT 1000").fetchall()]
    closed=[dict(x) for x in con.execute("SELECT trade_date,ticker,strategy_id,pnl FROM trades WHERE status='CLOSED'").fetchall()]
    con.close()
    pnlmap={(x["trade_date"],x["ticker"],x["strategy_id"]):x["pnl"] for x in closed}
    pts=[]
    for x in snaps:
        try:p=json.loads(x["payload"])
        except:continue
        if p.get("rsi3") is None or p.get("cp") is None or p.get("rvol") is None:continue
        pts.append({"date":x["trade_date"],"ticker":x["ticker"],"rsi":p["rsi3"],"cp":p["cp"],"rvol":p["rvol"],
                    "pnl":pnlmap.get((x["trade_date"],x["ticker"],"CEG"))})
    return jsonify({"points":pts})

@app.post('/api/backup')
def backup():
    stamp=now_ny().strftime("%Y%m%d_%H%M%S")
    bdir=DATA/"backups";bdir.mkdir(exist_ok=True)
    dbdst=bdir/f"arena_{stamp}.db";shutil.copy2(DB,dbdst)
    if CFG.exists():shutil.copy2(CFG,bdir/f"config_{stamp}.json")
    event(f"Backup created {dbdst.name}")
    return jsonify({"ok":True,"file":str(dbdst)})

@app.get('/api/export')
def export_bundle():
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,"w",zipfile.ZIP_DEFLATED) as z:
        if DB.exists():z.write(DB,"arena.db")
        if CFG.exists():z.write(CFG,"config.json")
        con=db()
        for name,query in {
          "signals.csv":"SELECT * FROM signals ORDER BY id",
          "trades.csv":"SELECT * FROM trades ORDER BY id",
          "snapshots.csv":"SELECT * FROM snapshots ORDER BY id",
          "strategy_journal.csv":"SELECT * FROM strategy_journal ORDER BY id",
          "midday_evals.csv":"SELECT * FROM midday_evals ORDER BY id",
          "contract_log.csv":"SELECT * FROM contract_log ORDER BY id",
          "api_log.csv":"SELECT * FROM api_log ORDER BY id",
          "events.csv":"SELECT * FROM events ORDER BY id",
          "shadow_trades.csv":"SELECT * FROM shadow_trades ORDER BY id",
          "debriefs.csv":"SELECT * FROM debriefs ORDER BY id"}.items():
            rows=con.execute(query).fetchall()
            if rows:
                cols=rows[0].keys()
                import csv
                sio=io.StringIO();w=csv.writer(sio);w.writerow(cols)
                for r in rows:w.writerow([r[c] for c in cols])
                z.writestr(name,sio.getvalue())
        try:
            z.writestr('research_metrics.json', json.dumps(compute_research_metrics(), default=str, indent=2))
            z.writestr('workspace.json', json.dumps(build_workspace(), default=str, indent=2))
        except Exception: pass
        tape=LIVE_DIR/now_ny().date().isoformat()/'tape.json'
        if tape.exists(): z.write(tape,f"live/{now_ny().date().isoformat()}/tape.json")
        con.close()
    mem.seek(0)
    return send_file(mem,mimetype="application/zip",as_attachment=True,download_name=f"paper_arena_export_{now_ny().strftime('%Y%m%d')}.zip")


@app.get('/api/strategies')
def strategies():
    con=db(); result=[]
    for s in STRATEGIES:
        r=con.execute("SELECT COUNT(*) n,SUM(CASE WHEN status='CLOSED' AND pnl IS NOT NULL THEN 1 ELSE 0 END) closed,SUM(CASE WHEN status='CLOSED' AND pnl IS NOT NULL AND pnl>0 THEN 1 ELSE 0 END) wins,SUM(CASE WHEN status='CLOSED' AND pnl IS NOT NULL THEN pnl ELSE 0 END) pnl,AVG(CASE WHEN status='CLOSED' THEN pnl END) avgp FROM trades WHERE strategy_id=?",(s['id'],)).fetchone(); sig=con.execute('SELECT COUNT(*) n FROM signals WHERE strategy_id=?',(s['id'],)).fetchone()['n']; result.append({**s,'stats':{**dict(r),'signals':sig}})
    con.close(); return jsonify({'strategies':result})
@app.get('/api/trades')
def trades():
    days=request.args.get('days')
    try: days=int(days) if days not in (None,'') else DESK_WINDOW_DAYS
    except (TypeError,ValueError): days=DESK_WINDOW_DAYS
    out,cutoff=desk_trades(days)
    return jsonify({'trades':out,'window_days':days,'cutoff':cutoff,'as_of':now_ny().isoformat()})

@app.get('/api/bootstrap')
def bootstrap():
    """One round-trip for the title-screen desk load: 30-day book + last known balance."""
    days=request.args.get('days')
    try: days=int(days) if days not in (None,'') else DESK_WINDOW_DAYS
    except (TypeError,ValueError): days=DESK_WINDOW_DAYS
    days=max(1,min(days,365))
    cutoff=desk_cutoff(days)
    acct=live_or_stored_account()
    rows,trade_cutoff=desk_trades(days)
    dash=dict(dashboard_payload())
    dash['curve']=[x for x in (dash.get('curve') or []) if (x.get('date') or '')>=cutoff]
    dash['dailyPnl']=[x for x in (dash.get('dailyPnl') or []) if (x.get('date') or '')>=cutoff]
    dash['balanceCurve']=balance_curve(days)
    dash['window_days']=days
    dash['cutoff']=cutoff
    return jsonify({
        'window_days':days,'cutoff':trade_cutoff,'as_of':now_ny().isoformat(),
        'status':status_payload(),
        'account':acct,
        'trades':rows,
        'dashboard':dash,
    })

def build_trade_pack(tr, pos=None):
    tr=dict(tr); date=tr.get('trade_date') or now_ny().date().isoformat(); sym=tr.get('ticker')
    mins=rth_bars(load_local_bars(sym,date,'1Min')) if sym else []
    orh,orl,_=opening_range(mins) if mins else (None,None,0)
    pv=0.0; vv=0.0; bars=[]
    for b in mins:
        h=float(b['h']); l=float(b['l']); c=float(b['c']); v=float(b.get('v') or 0)
        vw=b.get('vw'); typ=float(vw) if vw not in (None,'') else (h+l+c)/3.0
        pv+=typ*v; vv+=v
        try: dt=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY)
        except Exception: continue
        bars.append({'t':dt.isoformat(),'o':float(b['o']),'h':h,'l':l,'c':c,'v':v,'vwap':(pv/vv if vv else None)})
    atr1=None
    if len(bars)>=20:
        trs=[]
        for i in range(1,len(bars)):
            trs.append(max(bars[i]['h']-bars[i]['l'], abs(bars[i]['h']-bars[i-1]['c']), abs(bars[i]['l']-bars[i-1]['c'])))
        atr1=avg(trs[-14:]) if len(trs)>=14 else None
    for b in bars:
        if b.get('vwap') and atr1:
            b['vwap_hi']=b['vwap']+atr1; b['vwap_lo']=b['vwap']-atr1
    entry_dt=parse_ny(tr.get('entry_filled_at') or tr.get('signal_ts'))
    exit_dt=parse_ny(tr.get('exit_filled_at'))
    def idx(dt):
        if not dt or not bars:return None
        for i,b in enumerate(bars):
            try:
                if datetime.fromisoformat(b['t'])>=dt:return i
            except Exception: continue
        return len(bars)-1
    ei,xi=idx(entry_dt),idx(exit_dt)
    entry_px=bars[ei]['c'] if ei is not None else None
    last=bars[-1] if bars else None
    marked=attach_broker_mark(tr, pos)
    mark=marked.get('mark'); upl=marked.get('unrealized_pl')
    und_ret=None
    if entry_px and last and entry_px:
        und_ret=last['c']/entry_px-1
        if tr.get('direction')=='PUT': und_ret=-und_ret
    hyp=hyp_atm_pnl(tr, last['c'] if last else None, entry_px)
    lat=None
    a,b=parse_ny(tr.get('signal_ts')),parse_ny(tr.get('entry_filled_at'))
    if a and b: lat=(b-a).total_seconds()
    try: check=json.loads(tr.get('checklist') or '{}')
    except Exception: check={}
    mae,mfe=tr.get('mae'),tr.get('mfe')
    if mae is None or mfe is None:
        a2,b2=mae_mfe_from_tape(tr)
        mae=mae if mae is not None else a2; mfe=mfe if mfe is not None else b2
    return {'trade':tr,'bars':bars,'or_high':orh,'or_low':orl,'entryIndex':ei,'exitIndex':xi,
            'entryUnderlying':entry_px,'lastUnderlying':last['c'] if last else None,
            'mark':mark,'livePnl':upl,'directionalMove':und_ret,'hypAtmPnl':hyp,'latencySec':lat,
            'checklist':check,'contractScore':tr.get('contract_score'),'entrySpread':tr.get('entry_spread'),
            'mae':mae,'mfe':mfe,'iv':tr.get('entry_iv'),'delta':tr.get('entry_delta'),'gamma':tr.get('entry_gamma'),
            'exitKind':tr.get('exit_kind'),'abBook':tr.get('ab_book'),'fill':fill_quality(tr),
            'or_locked':True}

@app.get('/api/trade_board')
def trade_board():
    hit=mem_get('ui:board',10)
    if hit is not None: return jsonify(hit)
    con=db(); rows=[dict(x) for x in con.execute('SELECT * FROM trades ORDER BY id DESC LIMIT 8').fetchall()]; con.close()
    pos={}
    try:
        for x in broker_positions(): pos[x.get('symbol')]=x
    except Exception: pass
    packs=[build_trade_pack(r,pos) for r in rows]
    packs.sort(key=lambda p:(0 if p['trade'].get('status') in ('OPEN','ENTRY_SUBMITTED','EXIT_SUBMITTED') else 1, -(p['trade'].get('id') or 0)))
    out={'trades':packs}; mem_set('ui:board',out); return jsonify(out)

@app.get('/api/trade_chart/<int:tid>')
def trade_chart(tid):
    con=db(); tr=con.execute('SELECT * FROM trades WHERE id=?',(tid,)).fetchone(); con.close()
    if not tr: return jsonify({'error':'trade not found'}),404
    pos={}
    try:
        for x in broker_positions(): pos[x.get('symbol')]=x
    except Exception: pass
    return jsonify(build_trade_pack(dict(tr),pos))
@app.get('/api/signals')
def signals():
    con=db(); rows=[dict(x) for x in con.execute('SELECT * FROM signals ORDER BY id DESC LIMIT 200').fetchall()]; con.close(); return jsonify({'signals':rows})
@app.get('/api/events')
def events():
    con=db(); rows=[dict(x) for x in con.execute('SELECT * FROM events ORDER BY id DESC LIMIT 100').fetchall()]; con.close(); return jsonify({'events':rows})
@app.get('/api/live')
def live_tape():
    date=request.args.get('date') or now_ny().date().isoformat()
    hit=mem_get('ui:live',12)
    if hit is not None and hit.get('trade_date')==date: return jsonify(hit)
    overview=build_local_live_overview(date)
    overview['last_ingest']=meta_get('last_ingest')
    overview['last_midday_eval']=meta_get('last_midday_eval')
    overview['last_midday_scan']=meta_get('last_midday_scan')
    if 'coverage' not in overview:
        overview['coverage']=session_coverage(ALL_TICKERS,date)
        overview['session_complete_pct']=coverage_avg(overview['coverage'])
    con=db()
    overview['bar_count']=con.execute("SELECT COUNT(*) n FROM live_bars WHERE trade_date=? AND timeframe='1Min'",(date,)).fetchone()['n']
    overview['midday']=[dict(x) for x in con.execute("SELECT * FROM midday_evals WHERE trade_date=? ORDER BY strategy_id,ticker",(date,)).fetchall()]
    con.close()
    dnt={}
    for sym,st in (overview.get('tickers') or {}).items():
        r=do_not_trade_reasons(st, st.get('quote'))
        if r: dnt[sym]=r
    overview['dnt']=dnt
    overview['explain']=explain_now(live=overview, rm=mem_get('ui:rm:'+date,90) or {}, ws=mem_get('ui:workspace',30) or {})
    mem_set('ui:live',overview)
    return jsonify(overview)
@app.get('/api/explain')
def explain_api():
    date=now_ny().date().isoformat()
    live=mem_get('ui:live',20) or {}
    ws=mem_get('ui:workspace',20) or {}
    rm=mem_get('ui:rm:'+date,90) or {}
    return jsonify(explain_now(live=live, rm=rm, ws=ws))
@app.get('/api/live_bars/<sym>')
def live_bars(sym):
    sym=sym.upper(); date=request.args.get('date') or now_ny().date().isoformat()
    if sym not in ALL_TICKERS: return jsonify({'error':'unsupported ticker'}),400
    bars=rth_bars(load_local_bars(sym,date,'1Min'))
    st=local_intraday_state(sym,date)
    out=[]
    pv=0.0; vv=0.0
    for b in bars:
        h=float(b['h']); l=float(b['l']); c=float(b['c']); v=float(b.get('v') or 0)
        vw=b.get('vw'); typ=float(vw) if vw not in (None,'') else (h+l+c)/3.0
        pv+=typ*v; vv+=v
        vwap=pv/vv if vv else None
        out.append({'t':b['t'],'o':b['o'],'h':h,'l':l,'c':c,'v':v,'vwap':vwap,
                    'vwap_hi':(vwap+st['atr5']) if (vwap and st and st.get('atr5')) else None,
                    'vwap_lo':(vwap-st['atr5']) if (vwap and st and st.get('atr5')) else None})
    return jsonify({'ticker':sym,'date':date,'bars':out,'state':compact_state(st) if st else None,'path':str(LIVE_DIR/date/f'{sym}.json')})
@app.post('/api/ingest')
def ingest_now():
    try: return jsonify(ingest_live_data(force=True))
    except Exception as e: return jsonify({'error':str(e)}),500
@app.post('/api/preview')
def preview():
    out={'eod':None,'midday':None,'live':None,'errors':[]}
    try: out['eod']=evaluate_and_trade(True)
    except Exception as e: out['errors'].append('eod: '+str(e))
    try: out['midday']=evaluate_midday('ALL',True)
    except Exception as e: out['errors'].append('midday: '+str(e))
    try: out['live']=build_local_live_overview()
    except Exception as e: out['errors'].append('live: '+str(e))
    code=200 if (out['eod'] or out['midday']) else 500
    return jsonify(out),code
@app.post('/api/reconcile')
def rec():reconcile(); submit_due_exits(); return jsonify({'ok':True})

def build_workspace():
    date=now_ny().date().isoformat(); th=thresh(); clk=session_clock()
    try: vix_date,vix=latest_vix()
    except Exception: vix_date,vix=None,None
    try:
        tomorrow=next_trading_date(date)
        macros=macro_dates((now_ny().date()-timedelta(days=2)).isoformat(),(now_ny().date()+timedelta(days=10)).isoformat())
        macro_clear=tomorrow not in macros
    except Exception:
        macros=set(); macro_clear=None; tomorrow=None
    con=db()
    open_tr=[dict(x) for x in con.execute("SELECT * FROM trades WHERE status IN ('ENTRY_SUBMITTED','OPEN','EXIT_SUBMITTED') ORDER BY id DESC").fetchall()]
    closed=[dict(x) for x in con.execute("SELECT * FROM trades WHERE status='CLOSED' AND pnl IS NOT NULL").fetchall()]
    ev=[dict(x) for x in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 80").fetchall()]
    con.close()
    n=now_ny(); hm=n.strftime('%H:%M')
    playbook=[]
    for t in open_tr:
        horizon=t.get('horizon') or 'OVERNIGHT'
        if horizon=='EOD': due='15:50'; ready=hm>='15:50'
        else: due='09:35 next'; ready=False
        playbook.append({'id':t['id'],'strategy_id':t['strategy_id'],'ticker':t['ticker'],'option':t.get('option_symbol'),
                         'qty':t.get('qty'),'horizon':horizon,'exit_at':due,'ready':ready,'status':t.get('status'),
                         'score':t.get('contract_score'),'spread':t.get('entry_spread')})
    risk_premium=0.0
    for t in open_tr:
        try: risk_premium+=float(t.get('entry_fill') or 0)*100*int(t.get('qty') or 1)
        except Exception: pass
    codes={}
    for e in ev:
        if e.get('level') in ('WARN','ERROR'):
            k=e.get('code') or classify_error(e.get('message'))
            codes[k]=codes.get(k,0)+1
    by_sid={}
    for t in closed:
        by_sid.setdefault(t.get('strategy_id'),[]).append(float(t.get('pnl') or 0))
    boot={sid:bootstrap_expectancy(pn) for sid,pn in by_sid.items()}
    daily={}
    for t in closed:
        d=realized_date(t)
        daily.setdefault(d,{}).setdefault(t.get('strategy_id'),0)
        daily[d][t.get('strategy_id')]=daily[d][t.get('strategy_id')]+float(t.get('pnl') or 0)
    ids=[s['id'] for s in STRATEGIES]
    dates=sorted(daily)
    corr={a:{b:None for b in ids} for a in ids}
    for a in ids:
        for b in ids:
            xs=[]; ys=[]
            for d in dates:
                if a in daily[d] or b in daily[d]:
                    xs.append(daily[d].get(a,0.0)); ys.append(daily[d].get(b,0.0))
            if len(xs)>=4:
                try:
                    mx,my=avg(xs),avg(ys)
                    num=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
                    den=(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))**0.5
                    corr[a][b]=round(num/den,3) if den else None
                except Exception: corr[a][b]=None
    wf=[]
    all_closed=sorted(closed, key=realized_sort_key)
    pnls=[float(t.get('pnl') or 0) for t in all_closed]
    for i in range(5,len(pnls)):
        train=pnls[:i]; test=pnls[i]
        wf.append({'n':i,'train_exp':round(sum(train)/len(train),4),'next':round(test,4)})
    coverage=session_coverage(ALL_TICKERS,date)
    holes=sum(x.get('empty') or 0 for x in coverage.values())
    missing=sum(x.get('missing') or 0 for x in coverage.values())
    live_cached=mem_get('ui:live',20) or {}
    dnt={k:v for k,v in (live_cached.get('dnt') or {}).items() if v}
    ingest=meta_get('last_ingest'); stale=None
    if ingest:
        try: stale=(now_ny()-datetime.fromisoformat(ingest)).total_seconds()
        except Exception: pass
    skew=mem_get('ui:skew',30)
    if skew is None:
        skew=clock_skew(); mem_set('ui:skew',skew)
    hashes=mem_get('ui:barhash:'+date,180)
    if hashes is None:
        hashes=bar_integrity(date); mem_set('ui:barhash:'+date,hashes)
    mc=mem_get('ui:mc',30)
    if mc is None:
        mc=monte_carlo_open_book(open_tr, n=80); mem_set('ui:mc',mc)
    try:
        acct=broker_account(); pdt_warn=pdt_block('EOD')
        bp_info={'cash':acct.get('cash'),'buying_power':acct.get('buying_power'),
                 'options_buying_power':acct.get('options_buying_power'),'daytrade_count':acct.get('daytrade_count'),
                 'pattern_day_trader':acct.get('pattern_day_trader'),'pdt_warn':pdt_warn}
    except Exception:
        bp_info={'pdt_warn':None}
    hb=meta_get('heartbeat'); hb_age=None
    if hb:
        dt=parse_ny(hb)
        if dt: hb_age=(now_ny()-dt).total_seconds()
    con=db(); shadows=con.execute('SELECT COUNT(*) n FROM shadow_trades').fetchone()['n']; debrief=con.execute('SELECT * FROM debriefs WHERE trade_date=? ORDER BY id DESC LIMIT 1',(date,)).fetchone(); con.close()
    payload={
        'clock':clk,'thresholds':th,'vix':vix,'vix_date':vix_date,'macro_clear':macro_clear,'next_session':tomorrow,
        'fomc_near':bool(macros and any(abs((datetime.strptime(x,'%Y-%m-%d').date()-n.date()).days)<=2 for x in list(macros)[:40] if len(str(x))==10)),
        'cluster_n':cluster_count(date,20),'cluster_cap':th['max_cluster'],
        'daily_fires':{s['id']:daily_fire_count(s['id'],date) for s in STRATEGIES if s['id'] in MIDDAY_STRATEGY_IDS+EOD_STRATEGY_IDS},
        'max_daily_fires':th['max_daily_fires'],
        'playbook':playbook,'risk_if_zero':round(risk_premium,2),'open_n':len(open_tr),
        'errors':codes,'bootstrap':boot,'corr':corr,'corr_ids':ids,'walk_forward':wf[-12:],
        'integrity':{'holes':holes,'missing':missing,'coverage':coverage_avg(coverage),'stale_sec':stale,
                     'clock_skew':skew,'bar_hash':hashes},
        'dnt':{k:v for k,v in dnt.items() if v},
        'notes':{s['id']:{'name':s['name'],'desc':s['desc'],'plain':s.get('plain'),'author':s['author'],'session':s.get('session'),'invalidation':'Live nDays<30 or contract grade D'} for s in STRATEGIES},
        'bp':bp_info,'monte_carlo':mc,'shadow_n':shadows,
        'watchdog':{'heartbeat':hb,'age_sec':hb_age,'stale':bool(hb_age is None or hb_age>90)},
        'debrief':dict(debrief) if debrief else None,
        'guest': (not orders_allowed()) if True else False,
        'thresholds_b':cfg().get('thresholds_b') or {},
    }
    payload['explain']=explain_now(live=live_cached, rm=mem_get('ui:rm:'+date,90) or {}, ws=payload)
    return payload

@app.get('/api/workspace')
def workspace():
    hit=mem_get('ui:workspace',12)
    if hit is not None: return jsonify(hit)
    payload=build_workspace(); mem_set('ui:workspace',payload)
    return jsonify(payload)

@app.post('/api/thresholds')
def set_thresholds():
    d=request.get_json(force=True) or {}; c=cfg()
    th=c.get('thresholds') or {}
    for k in ('mvr_rvol','mvr_stretch','mvr_rsi_lo','mvr_rsi_hi','orb_rvol'):
        if k in d: th[k]=float(d[k])
    c['thresholds']=th
    if 'max_daily_fires' in d: c['max_daily_fires']=int(d['max_daily_fires'])
    if 'max_cluster' in d: c['max_cluster']=int(d['max_cluster'])
    if 'thresholds_b' in d and isinstance(d['thresholds_b'], dict):
        tb=c.get('thresholds_b') or {}
        for k,v in d['thresholds_b'].items(): tb[k]=v
        c['thresholds_b']=tb
    save_cfg(c)
    preview=None
    try:
        date=now_ny().date().isoformat()
        states={sym:local_intraday_state(sym,date) for sym in MIDDAY_TICKERS}
        states={k:v for k,v in states.items() if v}
        sigs,evals,ctx=midday_signals(states,'ALL',ignore_clock=True)
        preview={'would_fire':[{'strategy_id':s['strategy_id'],'ticker':s['ticker'],'direction':s['direction']} for s in sigs],
                 'n_evals':len(evals),'clock':ctx}
    except Exception as e:
        preview={'error':str(e)}
    return jsonify({'ok':True,'thresholds':thresh(),'preview':preview})

@app.route('/api/trades/<int:tid>', methods=['PATCH','POST'])
def patch_trade(tid):
    d=request.get_json(force=True) or {}
    con=db()
    if 'comment' in d:
        con.execute('UPDATE trades SET comment=? WHERE id=?',(str(d['comment'])[:400],tid))
    con.commit(); con.close(); return jsonify({'ok':True})

@app.post('/api/lab_snapshot')
def save_lab_snapshot():
    label=(request.get_json(silent=True) or {}).get('label') or now_ny().strftime('%H:%M')
    payload={'live':build_local_live_overview(),'metrics':compute_research_metrics(),'workspace':build_workspace()}
    con=db(); con.execute('INSERT INTO lab_snapshots(ts,trade_date,label,payload) VALUES(?,?,?,?)',
                          (now_ny().isoformat(),now_ny().date().isoformat(),label,json.dumps(payload,default=str)))
    con.commit(); sid=con.execute('SELECT last_insert_rowid() x').fetchone()['x']; con.close()
    return jsonify({'ok':True,'id':sid,'label':label})

@app.get('/api/lab_snapshots')
def list_lab_snapshots():
    con=db(); rows=[dict(x) for x in con.execute('SELECT id,ts,trade_date,label FROM lab_snapshots ORDER BY id DESC LIMIT 40').fetchall()]; con.close()
    return jsonify({'rows':rows})

@app.get('/api/lab_snapshots/<int:sid>')
def get_lab_snapshot(sid):
    con=db(); r=con.execute('SELECT * FROM lab_snapshots WHERE id=?',(sid,)).fetchone(); con.close()
    if not r: return jsonify({'error':'not found'}),404
    d=dict(r)
    try: d['payload']=json.loads(d.get('payload') or '{}')
    except Exception: pass
    return jsonify(d)

@app.get('/api/replay_live/<sym>')
def replay_live(sym):
    sym=sym.upper(); date=request.args.get('date') or now_ny().date().isoformat()
    if sym not in ALL_TICKERS: return jsonify({'error':'unsupported ticker'}),400
    bars=rth_bars(load_local_bars(sym,date,'1Min'))
    con=db()
    evs=[dict(x) for x in con.execute("SELECT * FROM midday_evals WHERE trade_date=? AND ticker=? ORDER BY ts",(date,sym)).fetchall()]
    con.close()
    out=[]
    for b in bars:
        try: dt=datetime.fromisoformat(str(b['t']).replace('Z','+00:00')).astimezone(NY)
        except Exception: continue
        out.append({'t':dt.isoformat(),'o':float(b['o']),'h':float(b['h']),'l':float(b['l']),'c':float(b['c']),'v':float(b.get('v') or 0)})
    return jsonify({'ticker':sym,'date':date,'bars':out,'evals':evs,'source':'local-sqlite'})

@app.post('/api/events/seen')
def mark_events_seen():
    con=db(); con.execute('UPDATE events SET seen=1 WHERE IFNULL(seen,0)=0'); con.commit(); con.close()
    return jsonify({'ok':True})

@app.get('/api/mtf/<sym>')
def mtf(sym):
    sym=sym.upper(); date=request.args.get('date') or now_ny().date().isoformat()
    if sym not in ALL_TICKERS: return jsonify({'error':'unsupported ticker'}),400
    m1=rth_bars(load_local_bars(sym,date,'1Min'))
    st=local_intraday_state(sym,date) or {}
    m5=st.get('bars5') or []
    ensure_daily_cache([sym],90)
    d1=load_local_bars_since(sym,'1Day',(now_ny().date()-timedelta(days=180)).isoformat())[-90:]
    def slim(arr):
        out=[]
        for b in arr:
            out.append({'t':b.get('t') or b.get('trade_date'),'o':b.get('o'),'h':b.get('h'),'l':b.get('l'),'c':b.get('c'),'v':b.get('v')})
        return out
    return jsonify({'ticker':sym,'date':date,'m1':slim(m1[-120:]),'m5':slim(m5[-80:]),'d1':slim(d1),
                    'or_high':st.get('or_high'),'or_low':st.get('or_low'),'or_locked':st.get('or_locked'),
                    'vwap':st.get('vwap'),'vwap_hi':st.get('vwap_hi'),'vwap_lo':st.get('vwap_lo')})

@app.get('/api/notes')
def get_notes():
    if not NOTES.exists():
        NOTES.write_text('# Lab notes\n\nSession observations live here.\n')
    return jsonify({'text':NOTES.read_text()})

@app.post('/api/notes')
def set_notes():
    d=request.get_json(force=True) or {}
    NOTES.write_text(str(d.get('text') or ''))
    return jsonify({'ok':True})

@app.post('/api/debrief')
def save_debrief():
    d=request.get_json(force=True) or {}
    date=now_ny().date().isoformat()
    con=db(); con.execute('INSERT INTO debriefs(ts,trade_date,q1,q2,q3) VALUES(?,?,?,?,?)',
                          (now_ny().isoformat(),date,str(d.get('q1') or '')[:500],str(d.get('q2') or '')[:500],str(d.get('q3') or '')[:500]))
    con.commit(); con.close()
    try:
        payload={'live':build_local_live_overview(),'metrics':compute_research_metrics(),'workspace':build_workspace(),'debrief':d}
        con=db(); con.execute('INSERT INTO lab_snapshots(ts,trade_date,label,payload) VALUES(?,?,?,?)',
                              (now_ny().isoformat(),date,'eod-debrief',json.dumps(payload,default=str))); con.commit(); con.close()
    except Exception as e: event(f'debrief snapshot: {e}','WARN')
    return jsonify({'ok':True})

@app.get('/api/shadow')
def shadow_book():
    con=db(); rows=[dict(x) for x in con.execute('SELECT * FROM shadow_trades ORDER BY id DESC LIMIT 200').fetchall()]; con.close()
    return jsonify({'rows':rows})

@app.get('/api/backups')
def list_backups():
    BACKUP_DIR.mkdir(exist_ok=True)
    files=sorted(BACKUP_DIR.glob('arena_*.db'), key=lambda p:p.stat().st_mtime, reverse=True)
    return jsonify({'files':[{'name':p.name,'mtime':datetime.fromtimestamp(p.stat().st_mtime, NY).isoformat(),'bytes':p.stat().st_size} for p in files[:40]]})

@app.post('/api/restore')
def restore_backup():
    d=request.get_json(force=True) or {}
    name=Path(str(d.get('name') or '')).name
    src=BACKUP_DIR/name
    if not src.exists() or not name.startswith('arena_') or not name.endswith('.db'):
        return jsonify({'error':'backup not found'}),404
    backup_db('pre-restore')
    shutil.copy2(src, DB)
    event(f'Restored {name}')
    return jsonify({'ok':True,'file':name})

@app.get('/api/journal')
def journal_day():
    date=request.args.get('date') or now_ny().date().isoformat()
    con=db()
    trades=[dict(x) for x in con.execute('SELECT * FROM trades WHERE trade_date=? ORDER BY id',(date,)).fetchall()]
    shadows=[dict(x) for x in con.execute('SELECT * FROM shadow_trades WHERE trade_date=? ORDER BY id',(date,)).fetchall()]
    debrief=con.execute('SELECT * FROM debriefs WHERE trade_date=? ORDER BY id DESC LIMIT 1',(date,)).fetchone()
    con.close()
    def row(t):
        return f"<tr><td>{t.get('id')}</td><td>{t.get('strategy_id')}</td><td>{t.get('ticker')}</td><td>{t.get('direction')}</td><td>{t.get('status')}</td><td>{t.get('entry_fill')}</td><td>{t.get('pnl')}</td><td>{t.get('mae')}</td><td>{t.get('mfe')}</td><td>{t.get('exit_kind') or ''}</td></tr>"
    html=f"""<!doctype html><html><head><meta charset=utf-8><title>ASH journal {date}</title>
    <style>body{{font-family:Georgia,serif;max-width:820px;margin:32px auto;color:#111}}h1{{font-size:22px}}table{{width:100%;border-collapse:collapse;font-size:12px}}td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left}}@media print{{button{{display:none}}}}</style></head>
    <body><button onclick="print()">Print / Save PDF</button>
    <h1>ASH paper journal · {date}</h1>
    <p>One-pager. Print this page to PDF from the browser.</p>
    <h2>Fills</h2><table><thead><tr><th>ID</th><th>Sid</th><th>Tkr</th><th>Side</th><th>Status</th><th>Entry</th><th>P&L</th><th>MAE</th><th>MFE</th><th>Exit</th></tr></thead>
    <tbody>{''.join(row(t) for t in trades) or '<tr><td colspan=10>No fills</td></tr>'}</tbody></table>
    <h2>Shadow skips</h2><table><thead><tr><th>Sid</th><th>Tkr</th><th>Status</th><th>Reason</th></tr></thead>
    <tbody>{''.join(f"<tr><td>{s.get('strategy_id')}</td><td>{s.get('ticker')}</td><td>{s.get('status')}</td><td>{s.get('skip_reason') or ''}</td></tr>" for s in shadows) or '<tr><td colspan=4>No skips</td></tr>'}</tbody></table>
    <h2>Debrief</h2><pre>{json.dumps(dict(debrief), indent=2) if debrief else 'Not submitted'}</pre>
    </body></html>"""
    return Response(html, mimetype='text/html')

init_db()
if __name__=='__main__':
    bind=(os.environ.get('CEG_BIND') or '0.0.0.0').strip() or '0.0.0.0'
    event(f'ASH Terminal web: http://{bind}:8765')
    app.run(host=bind,port=8765,debug=False,threaded=True)
