from datetime import datetime, timedelta, timezone
from app.coerce import instant
from app.errors import BusinessError

SHANGHAI = timezone(timedelta(hours=8))
CONFIRMED = 'CONFIRMED'
VERBAL = 'VERBAL'
STATUS_LABELS = {CONFIRMED: '医生确认', VERBAL: '中心口款待确认'}


def termination_day(entry):
    """终止日按 Asia/Shanghai 日历日归一，支持纯日期与带偏移时刻。"""
    text = str(entry.get('terminated_at', ''))
    try:
        if len(text) == 10:
            return datetime.strptime(text, '%Y-%m-%d').date()
        return instant(text).astimezone(SHANGHAI).date()
    except (ValueError, TypeError, BusinessError):
        raise ValueError('终止日期无法解析')


def visit_start_day(subject, visit, context):
    """取该受试者在入组生效方案下该访视的窗始日（相对入组的天数）。"""
    enrolled = instant(context['subjects'][subject]).astimezone(SHANGHAI).date()
    probe = datetime.combine(enrolled, datetime.min.time(), SHANGHAI).astimezone(timezone.utc)
    assignments = context['assignments'].get(subject, [])
    chosen = next((a['version'] for a in assignments
                   if instant(a['start']) <= probe < instant(a['end'])), None)
    if chosen and chosen in context['plans'] and visit in context['plans'][chosen]:
        return context['plans'][chosen][visit][0], chosen
    return None, None


def normalize_terminations(context):
    """把终止登记裁决为带状态的台账；非法登记进配置问题，绝不静默缩短应访。"""
    rows, issues = [], []
    for entry in context.get('terminations', []):
        subject = str(entry.get('subject', ''))
        status = entry.get('status')
        base = {'subject': subject, 'status': status,
                'terminated_at': entry.get('terminated_at', ''),
                'reported_by': entry.get('reported_by', ''), 'confirmed_by': entry.get('confirmed_by', '')}
        if subject not in context['subjects']:
            issues.append({**base, 'code': 'TERMINATION_UNKNOWN_SUBJECT'})
            continue
        if status not in STATUS_LABELS:
            issues.append({**base, 'code': 'TERMINATION_BAD_STATUS'})
            continue
        try:
            day = termination_day(entry)
        except ValueError:
            issues.append({**base, 'code': 'TERMINATION_BAD_DATE'})
            continue
        if day < instant(context['subjects'][subject]).astimezone(SHANGHAI).date():
            issues.append({**base, 'code': 'TERMINATION_BEFORE_ENROLL'})
            continue
        rows.append({**base, 'termination_day': day.isoformat(),
                     'affects_expected': status == CONFIRMED,
                     'status_label': STATUS_LABELS[status]})
    # 同一受试者保留全部登记，按终止日排序，页面可见口报与确认的演进
    rows.sort(key=lambda r: (r['subject'], r['termination_day']))
    return rows, issues


def build_visit_scope(context):
    """
    唯一次访范围裁决：
    - CONFIRMED 终止：窗始日晚于终止日的访视免除（终止日当天仍应访）；
    - VERBAL 口报：不免除任何访视，终止前缺口继续阻断；
    - 免除按 (subject, visit) 去重，重算/重试不会重复扣减。
    返回台账、免除集合、每格原因、配置问题。
    """
    rows, config_issues = normalize_terminations(context)
    confirmed = {}
    for row in rows:
        if row['affects_expected']:
            # 同一受试者多次确认时，以最早确认终止日为准（最保守，最不容易掩盖缺口）
            if row['subject'] not in confirmed or row['termination_day'] < confirmed[row['subject']]:
                confirmed[row['subject']] = row['termination_day']
    waived, reasons = set(), {}
    for subject, day_text in confirmed.items():
        term_day = datetime.strptime(day_text, '%Y-%m-%d').date()
        for visit in context['required_visits']:
            start_day, chosen = visit_start_day(subject, visit, context)
            if start_day is None:
                config_issues.append({'subject': subject, 'visit': visit,
                                      'code': 'TERMINATION_PLAN_UNRESOLVED'})
                continue
            enrolled = instant(context['subjects'][subject]).astimezone(SHANGHAI).date()
            window_start = enrolled + timedelta(days=start_day)
            key = (subject, visit)
            if window_start > term_day:
                if key not in waived:  # 幂等去重：同一终止重试不重复扣减
                    waived.add(key)
                    reasons[key] = {'subject': subject, 'visit': visit,
                                    'code': 'WAIVED_AFTER_TERMINATION',
                                    'termination_day': day_text,
                                    'window_start': window_start.isoformat(),
                                    'selected_protocol': chosen}
    for row in rows:
        if not row['affects_expected']:
            for visit in context['required_visits']:
                key = (row['subject'], visit)
                if key not in waived and key not in reasons:
                    reasons[key] = {'subject': row['subject'], 'visit': visit,
                                    'code': 'VERBAL_NOT_WAIVED',
                                    'termination_day': row['termination_day']}
    # 转为 JSON 可持久化的列表（格级原因），台账行单独返回
    cell_reasons = [{'subject': s, 'visit': v, **r} for (s, v), r in sorted(reasons.items())
                    if v is not None]
    return rows, waived, cell_reasons, config_issues
