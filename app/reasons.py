REASONS = {
    'COLUMN_COUNT':'列数错误', 'MISSING_ID':'编号缺失', 'DUPLICATE_CONFLICT':'重复编号冲突',
    'MISSING_VALUE':'数值缺失', 'BAD_NUMBER':'数值格式错误', 'BAD_TIME':'时间格式错误',
    'BAD_UNIT':'单位不受支持', 'UNKNOWN_REFERENCE':'引用对象不存在', 'INVALID_RANGE':'范围错误',
    'VERSION_CONFLICT':'版本冲突', 'EMPTY_FILE':'空文件', 'BLANK_FILE':'全空行',
    'HEADER_ONLY':'仅有表头', 'STALE_VERSION':'复核版本已更新', 'NOT_FOUND':'批次不存在',
    'WAIVED_AFTER_TERMINATION':'确认终止后访视免除', 'VERBAL_NOT_WAIVED':'口报终止未确认，不免除',
    'TERMINATION_UNKNOWN_SUBJECT':'终止登记受试者不存在', 'TERMINATION_BAD_STATUS':'终止状态无效',
    'TERMINATION_BAD_DATE':'终止日期无法解析', 'TERMINATION_BEFORE_ENROLL':'终止日早于入组日',
    'TERMINATION_PLAN_UNRESOLVED':'终止受试者方案窗无法解析',
}
def reject(state, record, code, detail):
    state['quarantine'].append({'line':record.get('_line',0),'id':record.get('id',''),
       'code':code,'detail':detail,'raw':{k:v for k,v in record.items() if not k.startswith('_')}})
