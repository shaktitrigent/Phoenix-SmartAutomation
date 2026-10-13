"""Describe explicit read-only collection lookups without retaining record values."""
import re
from urllib.parse import urlsplit,urlunsplit,parse_qsl
from phoenix_shared.record_verification import validate_record_lookup


def observe_record_lookup(response,application_url):
    if response.request.method!='GET':return []
    p=urlsplit(response.url);origin=urlsplit(application_url)
    if (p.scheme,p.hostname,p.port)!=(origin.scheme,origin.hostname,origin.port) or p.username or p.password:return []
    params=dict(parse_qsl(p.query,keep_blank_values=True))
    if any(re.search(r'token|secret|password|authorization|api.?key|session',k,re.I) for k in params):return []
    if 'offset' not in params or 'limit' not in params:return []
    try:limit=int(params['limit'])
    except (TypeError,ValueError):return []
    if not 1<=limit<=1000:return []
    try:payload=response.json()
    except Exception:return []
    arrays=[];totals=[]
    def visit(value,path):
        if isinstance(value,dict):
            for key,item in value.items():
                if isinstance(key,str):visit(item,path+[key])
        elif isinstance(value,list) and value and all(isinstance(v,dict) for v in value):arrays.append((path,value))
        elif type(value) is int and path and re.fullmatch(r'total|total_count|totalcount',path[-1],re.I):totals.append((path,value))
    visit(payload,[]);observations=[]
    for path,records in arrays:
        if not path:continue
        fields=set.intersection(*(set(record) for record in records))
        identities=[field for field in fields if re.search(r'id$|number$',field,re.I)
                    and all(type(record[field]) is int for record in records)
                    and len({record[field] for record in records})==len(records)]
        if len(identities)!=1:continue
        matching_totals=[t for t,n in totals if n>=len(records)]
        if len(matching_totals)!=1:continue
        lookup={'url':urlunsplit((p.scheme,p.netloc,p.path,'','')),'query':{k:v for k,v in params.items() if k not in {'offset','limit'}},
                'records_path':path,'total_path':matching_totals[0],'identity_paths':[[identities[0]]],
                'page_size':limit,'offset_parameter':'offset','limit_parameter':'limit'}
        validate_record_lookup(lookup)
        observations.append({'lookup':lookup,'record_fields':sorted(fields),'source':'observed_live_read_only_response'})
    return observations
