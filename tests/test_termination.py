import copy
from app.engine import evaluate
from app.modules.deviation.termination import build_visit_scope
from app.modules.deviation.rules import detect
from app.modules.locking.rules import decide


def term_ctx(base, entries):
    ctx = copy.deepcopy(base['context'])
    ctx['terminations'] = entries
    return ctx


def confirmed(subject, day):
    return {'subject': subject, 'status': 'CONFIRMED', 'terminated_at': day,
            'reported_by': '中心', 'confirmed_by': '研究医生'}


def verbal(subject, day):
    return {'subject': subject, 'status': 'VERBAL', 'terminated_at': day,
            'reported_by': '中心口报', 'confirmed_by': ''}


def test_confirmed_termination_shrinks_expected(clean):
    ctx = term_ctx(clean, [confirmed('00005', '2026-10-12')])  # V2 窗始 10-13 晚于终止日
    rows, waived, cells, issues = build_visit_scope(ctx)
    assert waived == {('00005', 'V2')}
    assert rows[0]['affects_expected'] is True
    assert any(c['code'] == 'WAIVED_AFTER_TERMINATION' and c['window_start'] == '2026-10-13' for c in cells)


def test_verbal_termination_never_waives(clean):
    # 裁决核心：口报缺医生确认，不缩短应访，防止掩盖终止前漏访
    ctx = term_ctx(clean, [verbal('00005', '2026-10-12')])
    rows, waived, cells, issues = build_visit_scope(ctx)
    assert waived == set()
    assert rows[0]['affects_expected'] is False
    assert all(c['code'] == 'VERBAL_NOT_WAIVED' for c in cells if c['subject'] == '00005')


def test_verbal_to_confirmed_only_then_waives(clean):
    ctx = term_ctx(clean, [verbal('00005', '2026-10-12')])
    assert build_visit_scope(ctx)[1] == set()
    ctx['terminations'][0]['status'] = 'CONFIRMED'
    ctx['terminations'][0]['confirmed_by'] = '研究医生'
    assert build_visit_scope(ctx)[1] == {('00005', 'V2')}


def test_window_start_day_still_due_boundary(clean):
    # 终止日当天访视窗已开启 → 仍应访；窗始日严格晚于终止日才免除
    same_day = term_ctx(clean, [confirmed('00005', '2026-10-13')])  # V2 窗始日
    assert build_visit_scope(same_day)[1] == set()
    before = term_ctx(clean, [confirmed('00005', '2026-10-12')])
    assert build_visit_scope(before)[1] == {('00005', 'V2')}


def test_pre_termination_gap_still_blocks(clean):
    # 终止前缺口不能被终止状态掩盖
    ctx = term_ctx(clean, [confirmed('00005', '2026-10-12')])
    _, waived, _, _ = build_visit_scope(ctx)
    windows = [r for r in clean['windows']
               if not (r['subject'] == '00005' and r['visit'] == 'V1')]  # 人为制造终止前漏 V1
    issues, done = detect(windows, ctx, waived)
    assert any(i['subject'] == '00005' and i['visit'] == 'V1'
               and i['code'] == 'MISSING_PRIMARY' for i in issues)
    assert ('00005', 'V2') in waived  # 终止后仍免除


def test_verbal_gap_blocks_but_confirmed_releases(clean):
    # 同一条终止：口报时 V2 缺口阻断；医生确认后同一缺口转为免除而放行
    windows = [r for r in clean['windows']
               if not (r['subject'] == '00005' and r['visit'] == 'V2')]
    v_ctx = term_ctx(clean, [verbal('00005', '2026-10-12')])
    _, v_waived, _, _ = build_visit_scope(v_ctx)
    v_issues, _ = detect(windows, v_ctx, v_waived)
    assert any(i['subject'] == '00005' and i['code'] == 'MISSING_PRIMARY' for i in v_issues)
    c_ctx = term_ctx(clean, [confirmed('00005', '2026-10-12')])
    _, c_waived, _, _ = build_visit_scope(c_ctx)
    c_issues, _ = detect(windows, c_ctx, c_waived)
    assert not any(i.get('subject') == '00005' for i in c_issues)


def test_recompute_is_idempotent_no_double_deduction(clean):
    ctx = term_ctx(clean, [confirmed('00005', '2026-10-12')])
    first = build_visit_scope(ctx)
    second = build_visit_scope(ctx)
    assert first[1] == second[1] == {('00005', 'V2')}
    # 同一终止重复登记也只扣减一次
    dup = term_ctx(clean, [confirmed('00005', '2026-10-12'), confirmed('00005', '2026-10-12')])
    assert build_visit_scope(dup)[1] == {('00005', 'V2')}


def test_post_termination_records_are_retained(clean):
    # 终止后完成的记录保留、不隔离、不判偏离
    assert any(r['subject'] == '00018' and r['visit'] == 'V2' for r in clean['records'])
    assert any(r['subject'] == '00018' and r['visit'] == 'V2' for r in clean['windows'])
    assert not any(d.get('subject') == '00018' for d in clean['deviations'])


def test_invalid_termination_blocks_instead_of_silent_release(clean):
    bad = term_ctx(clean, [
        {'subject': '99999', 'status': 'CONFIRMED', 'terminated_at': '2026-10-12'},
        {'subject': '00005', 'status': 'WEIRD', 'terminated_at': '2026-10-12'},
        {'subject': '00005', 'status': 'CONFIRMED', 'terminated_at': 'bad-date'},
        {'subject': '00005', 'status': 'CONFIRMED', 'terminated_at': '2026-09-01'},
    ])
    _, _, _, issues = build_visit_scope(bad)
    assert {x['code'] for x in issues} == {
        'TERMINATION_UNKNOWN_SUBJECT', 'TERMINATION_BAD_STATUS',
        'TERMINATION_BAD_DATE', 'TERMINATION_BEFORE_ENROLL'}
    state = copy.deepcopy(clean)
    state['context'] = bad
    rows, waived, cells, config_issues = build_visit_scope(bad)
    state['deviations'] = config_issues
    assert decide(state)['status'] == '待处理'
    assert decide(state)['termination_config_issues'] == 4


def test_sample_ledger_verbal_does_not_mask_real_gap(sample):
    # 现场批：00020 口报终止，但 V2 漏访仍按应访阻断；00018 医生确认才免除
    assert sample['waived_visits'] == [('00018', 'V2')]
    assert any(d.get('subject') == '00020' and d['code'] == 'MISSING_PRIMARY'
               for d in sample['deviations'])
    verbal_cells = [c for c in sample['termination_cells'] if c['code'] == 'VERBAL_NOT_WAIVED']
    assert all(c['subject'] == '00020' for c in verbal_cells)
    assert sample['balance']['expected'] == 39
    assert sample['balance']['status'] == '待处理'


def test_expected_identity_total_equals_expected_plus_waived(clean, sample):
    for state in (clean, sample):
        total = len(state['context']['subjects']) * len(state['context']['required_visits'])
        assert state['balance']['expected'] + state['balance']['waived_visits'] == total


def test_rule_version_invalidates_old_lock(clean, monkeypatch):
    from app import manifest
    from app.config import ROOT
    raw = (ROOT / 'sample_data' / 'clean.csv').read_bytes()
    monkeypatch.setattr(manifest, 'RULE_VERSION', '2026.11.17-r2')
    old_id = manifest.digest(raw, clean['context'])
    monkeypatch.setattr(manifest, 'RULE_VERSION', '2026.11.18-r3')
    new_id = manifest.digest(raw, clean['context'])
    assert old_id != new_id  # 同输入，规则换代即新批号，旧锁库结论失效


def test_api_override_verbal_then_confirmed(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, 'DB_PATH', str(tmp_path / 'term.sqlite'))
    c = TestClient(main.app)
    verbal = {'dataset': 'clean', 'overrides': {'terminations': [
        {'subject': '00005', 'status': 'VERBAL', 'terminated_at': '2026-10-12',
         'reported_by': '口报', 'confirmed_by': ''}]}}
    r1 = c.post('/api/runs', json=verbal).json()
    assert r1['balance']['waived_visits'] == 0
    assert r1['balance']['expected'] == 40
    confirmed = {'dataset': 'clean', 'overrides': {'terminations': [
        {'subject': '00005', 'status': 'CONFIRMED', 'terminated_at': '2026-10-12',
         'reported_by': '中心', 'confirmed_by': '研究医生'}]}}
    r2 = c.post('/api/runs', json=confirmed).json()
    assert r2['balance']['waived_visits'] == 1
    assert r2['balance']['expected'] == 39
    assert r2['balance']['status'] == '可锁库'
    assert r1['manifest']['run_id'] != r2['manifest']['run_id']
    # 同一终止重试不重复扣减
    r3 = c.post(f"/api/runs/{r2['manifest']['run_id']}/rerun", json={}).json()
    assert r3['manifest']['run_id'] == r2['manifest']['run_id']
    assert r3['balance']['waived_visits'] == 1
