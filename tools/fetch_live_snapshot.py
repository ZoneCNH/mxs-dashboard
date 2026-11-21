#!/usr/bin/env python3
"""MxS 宏观实测快照：fredpy PIT (vintage 2026-11-19) + Yahoo chart API。
口径：narratives.yaml transform=trend_20d + LGIP_NORMALIZATION_SPEC z-score
(2y 滚动 / pstdev / min 60)。jobless=w4 相对变化; vix/yield_curve 为展示口径。
"""
import sys, json, time, statistics, urllib.request, datetime
sys.path.insert(0, '/home/workspace/bytechainx/knowledge/framework/data_sources/fred')
from client import FredClient, FredAPIError

AS_OF = '2026-11-19'
TREND_OBS = 20
DIST_OBS = 504
MIN_OBS = 60

env = {}
for line in open('/home/workspace/bytechainx/.config/fredpy-mxs.env'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v
fred = FredClient('http://127.0.0.1:8000/api/v1',
                  env['FREDPY_MXS_CLIENT_ID'], env['FREDPY_MXS_CLIENT_SECRET'], timeout=30)

RATE = {'DFII10', 'T10YIE', 'BAMLH0A0HYM2', 'T10Y2Y'}
FRED_MAP = {
    'real_yield': 'DFII10', 'spx': 'SP500', 'breakeven': 'T10YIE',
    'hy_oas': 'BAMLH0A0HYM2', 'yield_curve': 'T10Y2Y',
    'jobless_claims': 'ICSA', 'vix': 'VIXCLS', 'oil': 'DCOILWTICO',
}
YAHOO_MAP = {'dxy': 'DX-Y.NYB', 'gold': 'GC=F', 'copper': 'HG=F'}
YAHOO_FALLBACK = {'spx': '^GSPC', 'vix': '^VIX'}  # 非 canonical 对照

def fred_series(sid):
    for attempt in range(4):
        try:
            r = fred._get('/pit', {'series_ids': sid, 'as_of': AS_OF, 'limit': 10000,
                                'observation_date_from': '2023-01-01'})
            break
        except FredAPIError as e:
            if e.status == 429 and attempt < 3:
                time.sleep(20 * (attempt + 1)); continue
            raise
    if r.get('truncated'):
        raise RuntimeError(f'truncated count={r.get("count")}')
    pts = {}
    for o in r.get('observations', []):
        v = o.get('value')
        if v in (None, '.', ''): continue
        pts[o['observation_date']] = float(v)
    return sorted(pts.items())

def yahoo_series(sym):
    url = (f'https://query2.finance.yahoo.com/v8/finance/chart/'
           f'{urllib.request.quote(sym, safe="")}?range=2y&interval=1d')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    d = json.load(urllib.request.urlopen(req, timeout=20))
    res = d['chart']['result'][0]
    ts = res['timestamp']; close = res['indicators']['quote'][0]['close']
    return sorted((datetime.datetime.fromtimestamp(t, datetime.UTC).strftime('%Y-%m-%d'), c)
                  for t, c in zip(ts, close) if c is not None)

def zscore(series, kind):
    """kind: price=trend20 相对变化; rate=trend20 差分; w4=4周相对变化(周频)"""
    vals = [v for _, v in series]
    trends = []
    if kind == 'w4':
        for i in range(4, len(vals)):
            trends.append(vals[i] / vals[i-4] - 1 if vals[i-4] else None)
    elif kind == 'price':
        for i in range(TREND_OBS, len(vals)):
            a, b = vals[i-TREND_OBS], vals[i]
            trends.append(b / a - 1 if a > 0 and b > 0 else None)
    else:
        for i in range(TREND_OBS, len(vals)):
            trends.append(vals[i] - vals[i-TREND_OBS])
    if any(t is None for t in trends[-MIN_OBS:]):
        return None, 'missing_samples'
    valid = [t for t in trends if t is not None]
    tail = valid[-DIST_OBS:]
    if len(tail) < MIN_OBS: return None, 'insufficient'
    sd = statistics.pstdev(tail)
    if sd == 0: return None, 'zero_variance'
    if valid[-1] is None: return None, 'missing_latest'
    return (valid[-1] - statistics.mean(tail)) / sd, 'computed'

out = {'as_of_fred_vintage': AS_OF,
       'generated_at': datetime.datetime.now(datetime.UTC).isoformat(),
       'spec': 'trend_20d + z(2y,pstdev,min60); jobless=w4rel z; vix/yield_curve=展示口径同法',
       'macro': {}, 'diagnostics': {}}

for key, sid in FRED_MAP.items():
    try:
        s = fred_series(sid)
    except Exception as e:
        out['diagnostics'][key] = f'fetch_err {str(e)[:120]}'; time.sleep(8); continue
    if not s:
        out['diagnostics'][key] = 'no_data'; time.sleep(8); continue
    kind = 'w4' if key == 'jobless_claims' else ('rate' if sid in RATE else 'price')
    z, why = zscore(s, kind)
    out['macro'][key] = round(z, 3) if z is not None else None
    out['diagnostics'][key] = {'series': sid, 'n': len(s), 'last_date': s[-1][0],
                               'last_value': s[-1][1], 'kind': kind, 'reason': why}
    print(f'fred {key} {sid}: z={out["macro"][key]} last={s[-1]}', file=sys.stderr)
    time.sleep(8)

for key, sym in {**YAHOO_FALLBACK, **YAHOO_MAP}.items():
    if key in out['macro'] and out['macro'][key] is not None:
        continue  # fredpy 已有实测值
    try:
        s = yahoo_series(sym)
    except Exception as e:
        out['diagnostics'][key] = f'fetch_err {str(e)[:120]}'; continue
    if not s:
        out['diagnostics'][key] = 'no_data'; continue
    z, why = zscore(s, 'price')
    out['macro'][key] = round(z, 3) if z is not None else None
    out['diagnostics'][key] = {'series': sym, 'n': len(s), 'last_date': s[-1][0],
                               'last_value': s[-1][1], 'kind': 'price', 'reason': why}
    print(f'yahoo {key} {sym}: z={out["macro"][key]} last={s[-1]}', file=sys.stderr)

raw = dict(out['macro'])
for k, v in out['macro'].items():
    if v is not None:
        out['macro'][k] = round(max(-1.0, min(1.0, v)), 3)
out['raw_z'] = raw

LGIP = {
 'L': [('real_yield',-0.45),('dxy',-0.35),('spx',0.20)],
 'G': [('spx',0.45),('real_yield',0.25),('gold',-0.20),('copper',0.10)],
 'I': [('breakeven',0.60),('gold',0.10),('oil',0.15),('real_yield',-0.15)],
 'P': [('dxy',0.34),('hy_oas',0.25),('spx',-0.26),('breakeven',-0.15)],
}
fac = {}
for f, comps in LGIP.items():
    vals = [out['macro'].get(k) for k, _ in comps]
    fac[f] = round(sum(w*v for (_, w), v in zip(comps, vals)), 3) if all(v is not None for v in vals) else None
out['lgip'] = fac

print(json.dumps(out, ensure_ascii=False, indent=1))
