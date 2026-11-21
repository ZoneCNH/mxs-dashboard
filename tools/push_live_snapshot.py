#!/usr/bin/env python3
"""把 fetch_live_snapshot.py 的产物写回 Lark Base「MxS 指标明细」实测-滚动行。

用法: python3 tools/push_live_snapshot.py [/path/to/mxs_live.json]
默认读 /tmp/mxs_live.json。只更新 已存在 的 11 条 实测-滚动 记录（按指标名匹配），
不新建记录；缺失指标跳过并在日志中报告。
"""
import json, os, shutil, subprocess, sys

BASE_TOKEN = 'A6nNb6UkSa28pSsJYghltjhKgeA'
TABLE_ID = 'tblN7oW8Qm5KTOPO'
SNAPSHOT = '实测-滚动'
LARK = shutil.which('lark-cli') or os.path.expanduser('~/.npm-global/bin/lark-cli')

SRC = {
    'real_yield': 'fredpy PIT DFII10', 'dxy': 'Yahoo DX-Y.NYB',
    'spx': 'Yahoo ^GSPC（非canonical对照）', 'yield_curve': 'fredpy PIT T10Y2Y',
    'jobless_claims': 'fredpy PIT ICSA', 'vix': 'Yahoo ^VIX（非canonical对照）',
    'breakeven': 'fredpy PIT T10YIE', 'gold': 'Yahoo GC=F（对照）',
    'oil': 'fredpy PIT DCOILWTICO', 'copper': 'Yahoo HG=F（对照）',
    'hy_oas': 'fredpy 未接入 BAMLH0A0HYM2',
}
LAST_DATE = {  # 观测截止日（写入来源备注）
    'real_yield': '2026-11-18', 'dxy': '2026-11-20', 'spx': '2026-11-20',
    'yield_curve': '2026-11-19', 'jobless_claims': '2026-11-14', 'vix': '2026-11-20',
    'breakeven': '2026-11-19', 'gold': '2026-11-20', 'oil': '2026-11-17',
    'copper': '2026-11-20', 'hy_oas': None,
}

def status(key, v):
    """与 index.html evalStatus 同口径：green→顺向 amber/neutral→中性 red→逆向/压力"""
    if key == 'real_yield': return '顺向' if v < -0.4 else ('逆向/压力' if v > 0.4 else '中性')
    if key == 'dxy':        return '顺向' if v < -0.3 else ('逆向/压力' if v > 0.5 else '中性')
    if key == 'spx':        return '顺向' if v > 0.4  else ('逆向/压力' if v < -0.6 else '中性')
    if key == 'yield_curve':return '顺向' if v > 0.2 else '中性'  # >0.2 green / <-0.4 amber / else neutral
    if key == 'jobless_claims': return '顺向' if v < -0.2 else ('逆向/压力' if v > 0.4 else '中性')
    if key == 'vix':        return '顺向' if v < -0.3 else ('逆向/压力' if v > 0.6 else '中性')
    if key == 'breakeven':  return '逆向/压力' if v > 0.4 else ('顺向' if v < -0.3 else '中性')
    if key == 'gold':       return '逆向/压力' if v > 0.5 else ('顺向' if v < -0.2 else '中性')
    if key == 'oil':        return '逆向/压力' if v > 0.5 else ('顺向' if v < -0.3 else '中性')
    if key == 'copper':     return '顺向' if v > 0.3  else ('逆向/压力' if v < -0.4 else '中性')
    if key == 'hy_oas':     return '逆向/压力' if v > 0.4 else ('顺向' if v < -0.3 else '中性')
    return '中性'

def lark(*args, payload=None):
    cmd = [LARK, 'base', *args, '--base-token', BASE_TOKEN]
    if payload is not None:
        cmd += ['--json', json.dumps(payload, ensure_ascii=False)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {'ok': False, 'raw': out.stdout[:300], 'stderr': out.stderr[:300]}

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else '/tmp/mxs_live.json'
    snap = json.load(open(src, encoding='utf-8'))
    macro, raw_z = snap['macro'], snap.get('raw_z', {})

    # 1) 拉全部记录，筛 出 实测-滚动 行，按指标名建映射
    res = lark('+record-list', '--table-id', TABLE_ID,
               '--field-id', '指标', '--field-id', '快照', '--limit', '200',
               '--format', 'json')
    if not res.get('ok'):
        sys.exit(f'record-list failed: {json.dumps(res, ensure_ascii=False)[:300]}')
    data = res['data']
    name2id = {}
    for row, rid in zip(data['data'], data['record_id_list']):
        name, sval = row[0], row[1]
        if isinstance(sval, list) and sval and sval[0] == SNAPSHOT:
            name2id[name] = rid
    print(f'live rows found: {len(name2id)}', file=sys.stderr)

    # 2) 构造更新：指标名 -> {数值, 状态, 来源}
    updates = {}
    missing = []
    for name, rid in name2id.items():
        key = name[name.rfind('（') + 1:-1]
        v = macro.get(key)
        fields = {}
        if v is None:
            fields['数值'] = None
            fields['状态'] = ['中性']
            fields['来源'] = f'{SRC.get(key, "?")}｜z=null（未接入）'
        else:
            fields['数值'] = v
            fields['状态'] = [status(key, v)]
            raw = raw_z.get(key)
            fields['来源'] = (f'{SRC.get(key, "?")}@{LAST_DATE.get(key) or "?"}'
                              f'｜raw_z={raw}（UI截断±1）')
        updates[rid] = fields
    if not updates:
        sys.exit('no live rows to update')

    res = lark('+record-batch-update', '--table-id', TABLE_ID,
               payload={'update_records': updates})
    ok = res.get('ok')
    print(json.dumps({'ok': ok, 'updated': len(updates),
                      'as_of': snap.get('as_of_fred_vintage'),
                      'generated_at': snap.get('generated_at'),
                      'lgip': snap.get('lgip')}, ensure_ascii=False))
    if not ok:
        sys.exit(f'batch-update failed: {json.dumps(res, ensure_ascii=False)[:400]}')

if __name__ == '__main__':
    main()
