"""Generation-to-capture requirements; never approve or replay UI operations."""
from urllib.parse import urlsplit, urlunsplit


def public_route(value):
    """Exclude query values, fragments and embedded credentials from diagnostics."""
    if not isinstance(value,str) or not value:return ''
    parsed=urlsplit(value)
    host=parsed.hostname or ''
    if ':' in host:host='['+host+']'
    try:
        if parsed.port is not None:host+=':'+str(parsed.port)
    except ValueError:return ''
    return urlunsplit((parsed.scheme,host,parsed.path,'',''))


def matches_context(captured_url, page_context):
    """A partial manual route must match segment boundaries, never another host."""
    if not captured_url or not page_context:return False
    captured=urlsplit(captured_url);context=urlsplit(page_context)
    if context.scheme or context.netloc:
        # Exact observed URLs are a different contract from partial manual paths.
        return public_route(captured_url)==public_route(page_context)
    expected=context.path.rstrip('/')
    actual=captured.path.rstrip('/')
    return bool(expected) and (actual==expected or actual.startswith(expected+'/'))


def capture_requirement(evidence, *, step, page_context, prerequisite_steps, application_url=None,
                        blocked_prerequisite_steps=(), action_index=None):
    """Describe where missing evidence is needed without promoting old selectors."""
    if not page_context:return None
    observations=(evidence.get('metadata') or {}).get('state_evidence') or [evidence]
    captured=[]
    for observation in observations:
        meta=observation.get('metadata') or {}
        cm=(observation.get('primary') or {}).get('metadata') or {}
        route=cm.get('validation_url') or meta.get('validation_url')
        same_origin=True
        if route and application_url:
            observed=urlsplit(route);application=urlsplit(application_url)
            same_origin=(observed.scheme.lower(),observed.netloc.lower())==(application.scheme.lower(),application.netloc.lower())
        if route and same_origin and matches_context(route,page_context):return None
        if route:captured.append(public_route(route))
    # An unknown provenance is also a capture requirement, not acceptance.
    return {'version':1,'step':step,'element_name':evidence.get('element_name'),
            'action_index':action_index,
            'preceding_action_indexes':list(range(1,action_index)) if action_index else [],
            'required_page_context':public_route(page_context),
            'captured_page_urls':sorted(set(captured)),
            'prerequisite_steps':list(prerequisite_steps),
            'blocked_prerequisite_steps':list(blocked_prerequisite_steps),
            'reason':'missing_current_page_locator_evidence',
            'requires_live_validation':True,'capture_status':'pending_runtime_resolution'}
