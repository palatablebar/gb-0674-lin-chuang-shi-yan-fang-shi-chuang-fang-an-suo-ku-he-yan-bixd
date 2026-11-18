def decide(state):
    c=state['counts']
    explained=len(state['records'])+len(state['quarantine'])+c['blank']+c['duplicate']+c['repeated_header']
    waived=len(state.get('waived_visits',()))
    expected=len(state['context']['subjects'])*len(state['context']['required_visits'])-waived
    config_issues=[r for r in state['deviations'] if str(r.get('code','')).startswith('TERMINATION_')]
    visit_issues=len(state['deviations'])-len(config_issues)
    blocked=visit_issues+len(state['retest_issues'])+len(state['quarantine'])+len(config_issues)
    gates=[]
    if visit_issues:gates.append({'code':'GATE_VISIT_GAP','detail':f'终止前访视缺口或偏离 {visit_issues} 项仍阻断'})
    if state['retest_issues']:gates.append({'code':'GATE_RETEST','detail':f'复检问题 {len(state["retest_issues"])} 项未裁决'})
    if state['quarantine']:gates.append({'code':'GATE_QUARANTINE','detail':f'采信隔离 {len(state["quarantine"])} 行未处理'})
    if config_issues:gates.append({'code':'GATE_TERMINATION_CONFIG','detail':f'终止登记配置问题 {len(config_issues)} 条'})
    if c['input']!=explained:gates.append({'code':'GATE_ROW_BALANCE','detail':'原始行守恒不成立'})
    if not gates:gates.append({'code':'GATE_PASS','detail':f'规定应访 {expected} 次全部完成，{waived} 次终止免除有医生确认依据'})
    return {'input':c['input'],'accepted':len(state['records']),'quarantined':len(state['quarantine']),
            'row_balanced':c['input']==explained,'completed':len(state['completed']),
            'expected':expected,'waived_visits':waived,
            'deviations':visit_issues,'retest_issues':len(state['retest_issues']),
            'termination_config_issues':len(config_issues),
            'blocked':blocked,'gates':gates,
            'status':'可锁库' if not blocked and c['input']==explained else '待处理'}
def apply(state):
    state['balance']=decide(state);state['views']['locking']={'title':'锁库闸门','rows':[state['balance']],'metrics':{'应访视':state['balance']['expected'],'已完成':state['balance']['completed'],'终止免除':state['balance']['waived_visits'],'阻断项':state['balance']['blocked']}}
