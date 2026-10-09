"""Conservative physical-target grouping, retaining every state observation."""
from __future__ import annotations
import json
from copy import deepcopy


def physical_key(bundle):
    meta = bundle.get('metadata') or {}
    candidate = bundle.get('primary') or {}
    cm = candidate.get('metadata') or {}
    data = meta.get('element_data') or cm.get('element_data') or {}
    ancestor = data.get('ancestor_context') or {}
    # Text and transient classes/values change during validation. Stable field
    # identity and structural scope must still agree; names alone never merge.
    identity = {k: data[k] for k in ('tag', 'id', 'name', 'type', 'role', 'placeholder', 'aria-label') if data.get(k)}
    scope = {k: ancestor[k] for k in ('container_tag', 'container_id', 'container_testid', 'container_class', 'section_context') if ancestor.get(k)}
    # A shared native name does not identify separate fields in different forms.
    # Keep textual scope when no stronger physical identifier establishes it.
    if data.get('tag') in {'input','select','textarea'} and not data.get('id') and not ancestor.get('container_id') and not ancestor.get('container_test_id') and not ancestor.get('container_testid'):
        section = ancestor.get('section_context') or {}
        if not any(section.get(k) for k in ('section_id','section_test_id','section_heading')):
            if ancestor.get('container_text'): scope['container_text'] = ancestor['container_text']
    if data.get('tag') in {'button','a','h1','h2','h3','h4','h5','h6','span','p'}:
        identity['text'] = data.get('text')
    if data.get('tag') in {'span','p'}:
        scope['container_text'] = ancestor.get('container_text')
    if (data.get('interaction_evidence') or {}).get('event') == 'click' and scope:
        identity['interaction_evidence'] = data['interaction_evidence']
    if data.get('tag')=='form' and (ancestor.get('container_id') or (ancestor.get('section_context') or {}).get('section_heading')):
        identity['scoped_form'] = True
    strong = bool(identity.get('id') or identity.get('name') or identity.get('scoped_form') or identity.get('interaction_evidence')
                  or (identity.get('text') and (ancestor.get('container_id') or ancestor.get('container_text') or scope.get('section_context'))))
    if not strong:
        identity = {'element_identity': meta.get('element_identity'), 'page': bundle.get('page')}
    return json.dumps([cm.get('validation_url') or meta.get('validation_url'), identity, scope,
                       None if strong else candidate.get('strategy'), None if strong else candidate.get('value')], sort_keys=True, default=str)


def group_state_evidence(bundles):
    from phoenix_shared.locator_policy import locator_accepted
    groups = {}
    for original in bundles:
        if not locator_accepted(original.get('primary') or {}, original.get('metadata')):
            accepted = next((c for c in original.get('alternates', []) if locator_accepted(c, original.get('metadata'))), None)
            if accepted is None:continue
            original = {**original, 'primary':accepted}
        key = physical_key(original)
        if key not in groups:
            groups[key] = deepcopy(original)
            groups[key].setdefault('metadata', {})['state_evidence'] = []
        result = groups[key]
        aliases = result['metadata'].setdefault('source_names', [])
        for name in [original.get('element_name'), *((original.get('metadata') or {}).get('source_names') or [])]:
            if name and name not in aliases:aliases.append(name)
        observations = (original.get('metadata') or {}).get('state_evidence') or [original]
        for observation in observations:
            observation = deepcopy(observation)
            observation.setdefault('metadata', {}).pop('state_evidence', None)
            if observation not in result['metadata']['state_evidence']:
                result['metadata']['state_evidence'].append(observation)
    for bundle in groups.values():
        observations=bundle['metadata']['state_evidence']
        candidates={}
        for observation in observations:
            candidate=observation['primary'];cm=candidate.get('metadata') or {}
            key=(candidate.get('strategy'),candidate.get('value'))
            entry=candidates.setdefault(key, {'candidate':candidate,'states':set()})
            entry['states'].add((cm.get('validation_url'),cm.get('state_name') or observation.get('page')))
        # Prefer evidence demonstrated in more states, rather than a weaker
        # one-state query whose apparent uniqueness disappears in later states.
        selected=max(candidates.values(),key=lambda c:len(c['states']))
        bundle['primary']=deepcopy(selected['candidate'])
    return list(groups.values())
