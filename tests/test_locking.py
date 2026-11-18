from app.modules.locking.rules import decide
from copy import deepcopy

def test_clean_lockable(clean):
    assert clean['balance']['status']=='可锁库'
def test_dirty_blocks(sample):
    assert sample['balance']['blocked']==7;assert sample['balance']['status']=='待处理'
def test_input_conservation(sample):
    assert sample['balance']['input']==51;assert sample['balance']['accepted']==45;assert sample['balance']['quarantined']==3;assert sample['balance']['row_balanced']
def test_completed_expected(clean):
    # 1 次医生确认终止免除（00018 V2），应访=完成=39
    assert clean['balance']['completed']==clean['balance']['expected']==39
    assert clean['balance']['waived_visits']==1
def test_isolation_blocks(clean):
    s=deepcopy(clean);s['quarantine']=[{'id':'x'}];assert decide(s)['status']=='待处理'
def test_count_mismatch_blocks(clean):
    s=deepcopy(clean);s['counts']['input']+=1;assert decide(s)['status']=='待处理';assert decide(s)['row_balanced'] is False
def test_missing_visit_not_replaced(sample):
    # 总访视 40 = 应访 39 + 终止免除 1；完成 37，缺口仍在
    assert sample['balance']['completed']==37
    assert sample['balance']['expected']+sample['balance']['waived_visits']==40
def test_gate_reasons_unique(sample,clean):
    codes=[g['code'] for g in sample['balance']['gates']]
    assert codes==list(dict.fromkeys(codes))  # 同一原因不重复列示
    assert any(g['code']=='GATE_VISIT_GAP' for g in sample['balance']['gates'])
    assert clean['balance']['gates'][0]['code']=='GATE_PASS'
