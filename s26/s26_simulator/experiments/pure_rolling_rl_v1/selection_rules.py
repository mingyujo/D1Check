def rolling_atc(bank):
 valid=[i for i,v in enumerate(bank['mask']) if v]
 smallest=min(bank['scores'][i] for i in valid)
 tied=[i for i in valid if bank['scores'][i]<=smallest+1e-12]
 return min(tied,key=lambda i:(-bank['x'][i][11],bank['actions'][i]['ordinal'],i))
