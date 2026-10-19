"""Fail closed for optional credit-consuming research; no API calls or ledger writes."""
from datetime import datetime
import math

def decide(request, balance, now, *, already_requested=False):
    """Callers must atomically reserve credits and record request IDs before dispatch."""
    def deny(reason):
        return {'allowed':False,'reason':reason,'route':'FREE_SOURCES'}
    if already_requested:return deny('DUPLICATE_REQUEST')
    if request.get('routine',True):return deny('ROUTINE_VIDIQ_DISABLED')
    if request.get('critical_gap') is not True or request.get('free_alternatives_exhausted') is not True:
        return deny('PUNCTUAL_NEED_UNPROVEN')
    if not request.get('request_id'):return deny('REQUEST_ID_REQUIRED')
    cost=request.get('maximum_credit_cost')
    remaining=balance.get('remaining')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in (cost,remaining)):
        return deny('UNKNOWN_OR_INVALID_COST_BALANCE')
    try:
        current=datetime.fromisoformat(now.replace('Z','+00:00'))
        observed=datetime.fromisoformat(balance['observed_at'].replace('Z','+00:00'))
        renewal=datetime.fromisoformat(balance['renews_at'].replace('Z','+00:00'))
        if any(v.tzinfo is None for v in (current,observed,renewal)):raise ValueError()
        age=(current-observed).total_seconds()
        if age<0 or age>3600 or current>=renewal:return deny('BALANCE_RECHECK_REQUIRED')
    except (KeyError,ValueError,TypeError):return deny('INVALID_BUDGET_TIMESTAMPS')
    if remaining-cost<25:return deny('EXISTING_25_CREDIT_RESERVE')
    return {'allowed':True,'reason':'PUNCTUAL_WITHIN_RESERVE',
            'route':'RESERVE_AND_RECORD_BEFORE_DISPATCH','maximum_credit_cost':cost}
