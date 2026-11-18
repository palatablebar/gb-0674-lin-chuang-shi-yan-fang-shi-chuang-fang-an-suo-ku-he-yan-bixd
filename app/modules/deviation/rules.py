from collections import defaultdict
from .termination import build_visit_scope

def detect(windows,context,waived=None):
    waived=waived or set()
    primary=defaultdict(list)
    for row in windows:
        if row['kind']=='PRIMARY':primary[(row['subject'],row['visit'])].append(row)
    issues=[];completed=[]
    for subject in sorted(context['subjects']):
        for visit in context['required_visits']:
            if (subject,visit) in waived:continue  # 确认终止后的访视免除，不算漏访
            items=primary.get((subject,visit),[])
            if not items:issues.append({'subject':subject,'visit':visit,'id':'','code':'MISSING_PRIMARY'});continue
            if len(items)>1:issues.append({'subject':subject,'visit':visit,'id':','.join(r['id'] for r in items),'code':'DUPLICATE_PRIMARY'});continue
            row=items[0]
            if row['code']!='IN_WINDOW':issues.append({**row,'code':'WINDOW_'+row['code']})
            else:completed.append(row)
    return issues,completed

def apply(state):
    rows,waived,cell_reasons,config_issues=build_visit_scope(state['context'])
    issues,completed=detect(state['windows'],state['context'],waived)
    # 终止配置问题本身阻断，避免错误配置静默放行锁库
    issues=issues+config_issues
    state.update(deviations=issues,completed=completed,terminations=rows,
                 waived_visits=sorted(waived),termination_cells=cell_reasons)
    waiver_rows=[r for r in cell_reasons if r.get('code')=='WAIVED_AFTER_TERMINATION']
    state['views']['deviation']={'title':'偏离复核','rows':issues,'metrics':{
        '完成访视':len(completed),'缺失或偏离':len(issues)-len(config_issues),
        '缺首次访视':sum(x['code']=='MISSING_PRIMARY' for x in issues),
        '终止免除访视':len(waiver_rows),'口款待确认':sum(not r['affects_expected'] for r in rows)}}
