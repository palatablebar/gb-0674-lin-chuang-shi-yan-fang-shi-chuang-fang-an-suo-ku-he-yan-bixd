from app.modules.deviation.rules import detect

def test_missing_primary_real(sample):
    assert any(r['subject']=='00020' and r['code']=='MISSING_PRIMARY' for r in sample['deviations'])
def test_late_deviation_real(sample):
    assert any(r['id']=='00001-V1' and r['code']=='WINDOW_LATE' for r in sample['deviations'])
def test_clean_completed_real(clean):
    # 00018 V2 经医生确认终止免除，完成数 40-1=39，且无偏离
    assert len(clean['completed'])==39;assert clean['deviations']==[]
def test_retest_cannot_fill_missing(clean):
    rows=[r for r in clean['windows'] if r['id']!='00001-V1'];issues,done=detect(rows,clean['context']);assert any(r['subject']=='00001' and r['visit']=='V1' and r['code']=='MISSING_PRIMARY' for r in issues)
def test_duplicate_primary_blocks(clean):
    rows=clean['windows']+[dict(clean['windows'][0],id='DUPLICATE')];issues,done=detect(rows,clean['context'],set(clean['waived_visits']));assert issues[0]['code']=='DUPLICATE_PRIMARY';assert len(done)==38
def test_order_invariant(clean):
    assert detect(clean['windows'],clean['context'],set(clean['waived_visits']))==detect(list(reversed(clean['windows'])),clean['context'],set(clean['waived_visits']))
def test_retest_not_counted_as_visit(clean):
    assert len([r for r in clean['windows'] if r['kind']=='RETEST'])==5;assert len(clean['completed'])==39
