"""Explicit, read-only record lookup for before/after creation verification."""
import os
import re
from urllib.parse import urlsplit


def validate_record_lookup(lookup):
    if not isinstance(lookup,dict) or not isinstance(lookup.get('url'),str) or not lookup['url']:
        raise ValueError('Record comparison needs an explicit lookup URL')
    for key in ('records_path','total_path'):
        if not isinstance(lookup.get(key),list) or not lookup[key] or not all(isinstance(v,str) and v for v in lookup[key]):
            raise ValueError('Record comparison needs explicit JSON paths')
    paths=lookup.get('identity_paths')
    if not isinstance(paths,list) or not paths or any(not isinstance(p,list) or not p or not all(isinstance(v,str) and v for v in p) for p in paths):
        raise ValueError('Record comparison needs stable identity paths')
    if type(lookup.get('page_size')) is not int or not 1<=lookup['page_size']<=1000:
        raise ValueError('Record comparison needs a bounded page size')
    if any(not isinstance(lookup.get(k),str) or not lookup[k] for k in ('offset_parameter','limit_parameter')):
        raise ValueError('Record comparison needs explicit pagination parameters')
    if lookup['offset_parameter']==lookup['limit_parameter']:
        raise ValueError('Pagination parameters must differ')
    if not isinstance(lookup.get('query',{}),dict):raise ValueError('Record lookup query must be an object')
    return lookup


def _path(value,path):
    for part in path:
        if not isinstance(value,dict) or part not in value:raise ValueError('Record lookup response does not match configured JSON paths')
        value=value[part]
    return value


def _expand(value):
    return re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}',lambda m:os.environ[m[1]],value) if isinstance(value,str) else value


def read_record_identities(page,lookup,*,max_pages=100):
    """Read complete pagination through the current context; never mutate data."""
    validate_record_lookup(lookup)
    url=_expand(lookup['url']);current=urlsplit(page.url);destination=urlsplit(url)
    origin=lambda p:(p.scheme,p.hostname,p.port or (443 if p.scheme=='https' else 80))
    if destination.scheme not in {'http','https'} or destination.username or destination.password or origin(current)!=origin(destination):
        raise ValueError('Record lookup must use the current application origin')
    identities=set();total=None;offset=0
    for _ in range(max_pages):
        params={k:_expand(v) for k,v in lookup.get('query',{}).items()}
        params.update({lookup['offset_parameter']:offset,lookup['limit_parameter']:lookup['page_size']})
        response=page.context.request.get(url,params=params,timeout=30000,max_redirects=0)
        if not response.ok:raise AssertionError('Configured record lookup failed; verify authentication and endpoint')
        payload=response.json();records=_path(payload,lookup['records_path']);observed_total=_path(payload,lookup['total_path'])
        if not isinstance(records,list) or type(observed_total) is not int or observed_total<0:
            raise ValueError('Record lookup needs a list and a nonnegative integer total')
        if total is None:total=observed_total
        elif total!=observed_total:raise AssertionError('Record collection changed during paginated observation')
        if len(records)>lookup['page_size']:raise ValueError('Record lookup ignored its configured page size')
        for record in records:
            identity=tuple(_path(record,path) for path in lookup['identity_paths'])
            if any(type(v) not in (str,int) or v=='' for v in identity):raise ValueError('Record identity must contain stable scalar values')
            if identity in identities:raise AssertionError('Duplicate record identity or repeated pagination page')
            identities.add(identity)
        offset+=len(records)
        if offset==total:return frozenset(identities)
        if offset>total or not records:raise AssertionError('Incomplete or inconsistent record collection')
    raise AssertionError('Record lookup exceeded its bounded pagination limit')


def assert_no_new_records(page,lookup,baseline):
    if not isinstance(baseline,frozenset):raise ValueError('Non-creation needs a captured record baseline')
    after=read_record_identities(page,lookup)
    if after-baseline:raise AssertionError('New record identities appeared after the invalid submission')
