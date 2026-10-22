"""Two deterministic selectors with no network, fitted weights, or RL history."""
def cost_rule(bank):
    valid=[i for i,v in enumerate(bank['mask']) if v]
    smallest=min(bank['scores'][i] for i in valid)
    tied=[i for i in valid if bank['scores'][i]<=smallest+1e-12]
    return min(tied,key=lambda i:(-bank['x'][i][11],bank['actions'][i]['ordinal'],i))

def teacher_rule(bank):
    valid=[i for i,v in enumerate(bank['mask']) if v]
    preferred=[i for i in valid if bank['actions'][i]['kind']=='DISPATCH' and bank['x'][i][31]>.5]
    if preferred:return min(preferred,key=lambda i:(bank['x'][i][8],bank['actions'][i]['ordinal'],i))
    event=[i for i in valid if bank['actions'][i]['kind']=='WAIT_EVENT']
    if not event:raise ValueError('No physical preferred dispatch or active-owner wait')
    return event[0]
