"""Evidence-aware fallback compiler; no website-specific selectors or credentials."""
from __future__ import annotations
import re
from pydantic import ValidationError
from phoenix_shared.locator_policy import locator_accepted
from phoenix_shared.models.locator import Locator
from phoenix_shared.generation_contract import Snapshot, words, clauses, outcome_contract, summary_binding
from phoenix_shared.automation_translation import assertion_lines, explicit_step_data, fill_value_expression
from phoenix_shared.manual_semantics import bound_actions, expectation_parts

FILLER={'the','field','input','button','element','form','supplied','registered','valid','invalid','incorrect','value'}


def control_compatible(data, kind):
    # Legacy accepted records may lack native semantics. Keep their historical
    # compatibility; execution still requires fresh physical identity evidence.
    if not data.get('tag') and not data.get('role'):return True
    tag=data.get('tag');role=data.get('role');input_type=str(data.get('type') or 'text').lower()
    button=tag=='button' or role=='button' or (tag=='input' and input_type in {'button','submit','reset','image'})
    link=role=='link' or (tag=='a' and bool(data.get('href')))
    if kind=='input':return tag=='textarea' or (tag=='input' and input_type not in {'button','submit','reset','image','checkbox','radio','file','hidden'})
    if kind=='button':return button
    if kind=='link':return link
    if kind in {'interaction','menuitem'}:return button or link or role=='menuitem' or (data.get('interaction_evidence') or {}).get('event')=='click'
    return True


def select_subject(target,action,bundles,snapshot,kind):
    wanted=set(words(target))-FILLER
    scope_match=re.search(r'([\w-]+)\s+form',action,re.I)
    scope_name=scope_match.group(1) if scope_match else None
    if scope_name and wanted-set(words(scope_name)):wanted-=set(words(scope_name))
    if not wanted:return None
    matches=[];scores={}
    for bundle in bundles:
        candidates=[bundle.get('primary'),*(bundle.get('alternates') or [])]
        candidate = None
        for raw_candidate in candidates:
            if not isinstance(raw_candidate, dict):
                continue
            # Persistence stores the identity on the enclosing bundle. Restore
            # it on a copy without changing selector or validation evidence.
            normalized = dict(raw_candidate)
            if not normalized.get('element_name'):
                normalized['element_name'] = bundle.get('element_name')
            try:
                parsed = Locator.model_validate(normalized)
            except ValidationError:
                # A malformed candidate cannot become accepted evidence; a
                # valid alternate or a fresh snapshot may still resolve it.
                continue
            if locator_accepted(normalized, bundle.get('metadata')):
                candidate = parsed
                break
        if candidate is None:continue
        data=(bundle.get('metadata') or {}).get('element_data') or {}
        ancestor=data.get('ancestor_context') or {}
        section=ancestor.get('section_context') or {}
        # Captured ancestry supplies the scope even when a control has only a
        # generic name (e.g. PasswordInput). Do not discard that evidence.
        aliases=' '.join([str(bundle.get('element_name','')),str(data.get('name','')),str(data.get('placeholder','')),
                          str(data.get('aria-label','')),str(data.get('text','')),
                          str(data.get('id','')),str(data.get('data') or {}),
                          str(ancestor.get('container_id','')),str(ancestor.get('container_class','')),
                          str(ancestor.get('container_text','')),
                          str(section.get('section_id','')),str(section.get('section_class','')),
                          str(section.get('section_heading',''))])
        tokens=set(words(aliases))
        tag=data.get('tag')
        role=data.get('role')
        if not control_compatible(data,kind):continue
        if kind=='link' and not (tag=='a' or role=='link' or 'link' in tokens):continue
        if kind=='input' and not tag and {'button','link'} & tokens:continue
        if kind=='input' and tag and tag not in {'input','textarea','select'}:continue
        if kind=='heading' and not (tag in {'h1','h2','h3','h4','h5','h6'} or role=='heading'):continue
        if kind=='form' and tag!='form' and role!='form':continue
        if kind=='message' and (tag in {'form','input','textarea','select','button','a','h1','h2','h3','h4','h5','h6'} or role in {'form','heading','button','menuitem'}):continue
        if kind=='select' and tag!='select' and not ({'dropdown','select','combobox'} & tokens):continue
        if kind=='checkbox' and data.get('type')!='checkbox' and 'checkbox' not in tokens:continue
        if wanted<=tokens and (not scope_name or set(words(scope_name))<=tokens):
            expression = candidate.to_playwright()
            matches.append(expression)
            profiles=[set(words(v))-FILLER for v in (bundle.get('element_name',''),data.get('name',''),data.get('placeholder',''),data.get('aria-label',''),data.get('text',''),data.get('id',''))]
            score=max([(1,-len(p-wanted)) for p in profiles if wanted<=p] or [(0,-len(tokens-wanted))])
            scores[expression]=max(scores.get(expression,score),score)
            snapshot.evidence.setdefault(expression, []).append(bundle)
    # Matching text/selector alone is not enough to merge different physical
    # targets. Only the shared structural evidence grouping may deduplicate.
    from phoenix_shared.state_evidence import physical_key
    if scores:
        best=max(scores.values());matches=[expression for expression in matches if scores[expression]==best]
    physical={physical_key(b) for expression in matches for b in snapshot.evidence.get(expression, [])}
    matches=list(dict.fromkeys(matches))
    if len(physical)>1:return None
    if len(matches)==1:return matches[0]
    if len(matches)>1:return None
    form,scope=snapshot.form(scope_name) if scope_name else (None,None)
    if scope_name and not scope:return None
    controls=[]
    for node in snapshot.nodes:
        if form is not None and not snapshot.inside(node,form):continue
        if not control_compatible({'tag':node['tag'],**node['attrs']},kind):continue
        if kind=='input' and node['tag'] not in {'input','textarea','select'}:continue
        if kind=='select' and node['tag']!='select':continue
        if kind=='checkbox' and not (node['tag']=='input' and node['attrs'].get('type')=='checkbox'):continue
        if kind=='link' and not (node['tag']=='a' or node['attrs'].get('role')=='link'):continue
        attrs=node['attrs']
        tokens=set(words(' '.join([attrs.get('id',''),attrs.get('name',''),attrs.get('placeholder',''),attrs.get('aria-label',''),node['text']])))
        parent=node.get('parent')
        nearest_form=None
        while parent:
            if parent['tag']=='form':
                nearest_form=parent
                break
            parent=parent.get('parent')
        observed_scope=None
        if nearest_form:
            # A manual field label can itself name its form, without saying
            # "inside ... form". Use observed form buttons to bind that scope.
            for button in snapshot.nodes:
                if button['tag']=='button' and snapshot.inside(button,nearest_form):
                    tokens.update(words(button['text']))
                    identified,expression=snapshot.form(button['text'])
                    if identified is nearest_form:
                        observed_scope=expression
        if wanted<=tokens:controls.append((node,observed_scope))
    if len(controls)!=1:return None
    node,observed_scope=controls[0];attrs=node['attrs'];root=scope or observed_scope or 'page'
    def propose(expression):
        data={'tag':node['tag'], **{k:v for k,v in attrs.items() if k in
            {'id','name','type','role','placeholder','aria-label','data-testid','data-test'}}}
        data['data']={k:v for k,v in attrs.items() if k.startswith('data-')}
        if node['tag'] in {'a','button'}:data['text']=' '.join(node['text'].split())
        parent=node.get('parent')
        while parent and parent['tag']!='form':parent=parent.get('parent')
        if parent:
            data['ancestor_context']={'container_tag':'form','container_id':parent['attrs'].get('id',''),
                'container_class':parent['attrs'].get('class',''), 'container_text':' '.join(parent['text'].split())}
        snapshot.proposals.append({'element_name':target,'expression':expression,'element_data':data})
        return expression
    # Snapshot-derived candidates are not declared accepted. The existing live
    # acceptance/Expert gate must validate them before any generated action runs.
    if attrs.get('data-testid'):return propose(f"{root}.get_by_test_id({attrs['data-testid']!r})")
    if attrs.get('placeholder'):return propose(f"{root}.get_by_placeholder({attrs['placeholder']!r}, exact=True)")
    if attrs.get('aria-label'):return propose(f"{root}.get_by_label({attrs['aria-label']!r}, exact=True)")
    if (node['tag'] in {'button','a'} or attrs.get('role') in {'button','link'}) and node['text'].strip():
        role=attrs.get('role') or ('button' if node['tag']=='button' else 'link')
        return propose(f"{root}.get_by_role({role!r}, name={' '.join(node['text'].split())!r}, exact=True)")
    if attrs.get('id') and re.fullmatch(r'[\w-]+',attrs['id']):
        return propose(f"{root}.locator({('[id=\"'+attrs['id']+'\"]')!r})")
    if attrs.get('name') and re.fullmatch(r'[\w-]+',attrs['name']):
        return propose(f"{root}.locator({(node['tag']+'[name="'+attrs['name']+'"]')!r})")
    return None


def compile_fallback(manual,url,bundles,html,*,extract_fill,extract_click,split_actions,test_name,missing_fill_data,extract_select,environment_values=None):
    from phoenix_shared.state_evidence import group_state_evidence
    bundles=group_state_evidence(bundles)
    snapshot=Snapshot(html);snapshot.evidence={};lines=[];contracts=[];unresolved=[];step_records=[];previous_expected=[];pending_completion=[];last_navigation_binding=None
    fields=[];step_operations=[]
    def target_evidence(expression):
        matches=snapshot.evidence.get(expression, [])
        if not matches:return None
        # Same selector observations (e.g. expanded/collapsed trigger) keep
        # their separate descriptors for current-state identity validation.
        result={**matches[0], 'metadata':dict(matches[0].get('metadata') or {})}
        observations=[]
        for match in matches:
            for original in (match.get('metadata') or {}).get('state_evidence', [match]):
                meta=original.get('metadata') or {}
                cm=(original.get('primary') or {}).get('metadata') or {}
                compact={'element_name':original['element_name'],'page':original.get('page'),
                         'primary':{**original['primary'], 'metadata':{k:v for k,v in cm.items() if k in {'source','stability','stability_score','match_count','identity_matches','validation_url','state_name'}}},
                         'metadata':{'element_data':meta.get('element_data') or cm.get('element_data'),
                                     'element_identity':meta.get('element_identity'),'state_name':meta.get('state_name')}}
                if compact not in observations:observations.append(compact)
        result['metadata']={'state_evidence':observations}
        result['primary']={**result['primary'],'metadata':observations[0]['primary']['metadata']}
        result.pop('alternates',None)
        return result
    def check_target(expression):
        evidence=target_evidence(expression)
        return ['    validate_target(page, '+repr(evidence)+')'] if evidence else []
    def explicit_contract(expectation, action, number):
        # Each positive expectation must name a physical target. Repeated text
        # is resolved with its supplied field-group qualifier, never globally.
        quoted=re.findall(r'"([^"]*)"|\x27([^\x27]*)\x27|`([^`]*)`', expectation)
        values=[next((v for v in group if v), '') for group in quoted]
        field_match=re.search(r'(?:the\s+)?([\w -]+?)\s+field\s+(?:contains|remains|is empty)',expectation,re.I)
        kind=None;label=None;expected_value=None
        if field_match:
            label=re.sub(r'^the\s+', '', field_match[1],flags=re.I);kind='input'
            expected_value="" if re.search(r'\bempty\b',expectation,re.I) else values[0] if values else None
            if expected_value is None:return None
        elif re.search(r'\bvisible\b',expectation,re.I) and not re.search(r'\b(?:not|no)\b',expectation,re.I):
            if re.search(r'field\b',expectation,re.I) and not re.search(r'message',expectation,re.I):
                label=re.sub(r'\s+(?:is|are) visible[.;]?$', '', expectation,flags=re.I)
                label=re.sub(r'^the\s+|\s+field$', '', label,flags=re.I);kind='input'
            elif 'form' in expectation.lower():
                label=re.search(r'(\w+)\s+form',expectation,re.I).group(1)+' form';kind='form'
            elif not values and re.search(r'\bbutton\b',expectation,re.I):
                label=re.sub(r'\s+(?:is|are) visible[.;]?$', '',expectation,flags=re.I)
                label=re.sub(r'^the\s+|\s+button$', '',label,flags=re.I);kind='button'
            elif values:
                label=values[0];kind='heading' if 'heading' in expectation.lower() else 'menuitem' if re.search(r'\bmenu item\b|\boption\b.*\bmenu\b',expectation,re.I) else 'button' if 'button' in expectation.lower() else 'message'
                scope=re.search(r'within (?:the )?([\w -]+?) field group',expectation,re.I)
                if scope:label=scope[1]+' '+label
        if label is None:return None
        from phoenix_shared.automation_translation import environment_reference
        label_reference=environment_reference(label) if kind=='heading' else None
        if label_reference:
            label=(environment_values or {}).get(label_reference)
            if not label:return None
        subject=select_subject(label,expectation,bundles,snapshot,kind)
        if not subject:return None
        spec={'version':1,'step':number,'kind':'value' if expected_value is not None else 'visible',
              'subject':subject,'scope':None,'source':'manual_expected_result','expected_text':expectation,'action_text':action}
        evidence=target_evidence(subject)
        if evidence:spec['target_evidence']=evidence
        if expected_value is not None:spec['expected_value']=expected_value
        if label_reference:spec['expected_heading_reference']=label_reference
        return spec
    def contract_line(spec):
        contracts.append(spec)
        suffix=', reference_url='+spec['reference_binding'] if spec.get('kind')=='url_unchanged' else ''
        return '    assert_contract(page, '+repr(spec)+suffix+')'
    for index,step in enumerate(manual.get('steps',[]),1):
        number=step.get('step_number',index);raw=step.get('action','');expected=step.get('expected_result','')
        actions=[part for action in bound_actions(raw,step.get('test_data','')) for part in split_actions(action)]
        emitted=[];target=None;value=None;action_kind=None;failures=[];requested_target=None;unsupported=[]
        if not actions:failures.append('missing_explicit_action_data')
        for atomic in actions:
            action=explicit_step_data(atomic,step.get('test_data',''))
            action = re.sub(r'^In\s+[^,]+,\s*', '', action, flags=re.I)
            low=action.lower();lines.append(f'    # Step {number}')
            if re.match(r'open\b',low) and not re.search(r'https?://|\b(?:url|page|website|site)\b',low):
                label=re.sub(r'^open\s+(?:the\s+)?', '', action,flags=re.I)
                target=select_subject(label,raw,bundles,snapshot,'interaction')
                if not target:requested_target=label;failures.append('missing_or_ambiguous_click_target');continue
                emitted.extend(check_target(target))
                emitted.append(f'    click_ready(page, {target}, {label!r})');action_kind='click'
            elif re.match(r'(?:navigate|visit|go|open)\b',low):
                urls=re.findall(r'https?://[^\s`"\']+',action)
                destination=urls[0].rstrip('.,') if urls else url
                if not destination:failures.append('missing_navigation_url');continue
                emitted.append(f'    page.goto({destination!r}, wait_until="domcontentloaded")')
                last_navigation_binding=f'_phoenix_navigation_url_{number}'
                emitted.append(f'    {last_navigation_binding} = page.url')
                action_kind='goto'
            elif re.match(r'clear\b|leave\b.*\bempty\.?$', low):
                field = re.sub(r'^clear\s+(?:the\s+)?|\s+field\.?$', '', action, flags=re.I)
                if low.startswith('leave'):
                    field=re.sub(r'^leave\s+(?:the\s+)?|\s+field\s+empty\.?$', '',action,flags=re.I)
                target=select_subject(field,raw,bundles,snapshot,'input')
                if not target:requested_target=field;failures.append('missing_or_ambiguous_fill_target');continue
                value="''"
                if field not in fields:fields.append(field)
                emitted.extend(check_target(target))
                emitted.append(f'    fill_ready(page, {target}, {value}, {field!r})')
                action_kind='fill'
            elif re.match(r'(?:enter|fill|type|input|provide)\b',low):
                if missing_fill_data(action):failures.append('missing_explicit_fill_data');continue
                field,raw_value=extract_fill(action)
                if re.match(r'(?:the )?(?:supplied|provided|registered|valid|invalid|incorrect)\b',raw_value,re.I) and not any(q+raw_value+q in action for q in ("'", '"', '`')):
                    failures.append('missing_explicit_fill_data');continue
                value=fill_value_expression(raw_value)
                target=select_subject(field,raw,bundles,snapshot,'input')
                if not target:requested_target=field;failures.append('missing_or_ambiguous_fill_target');continue
                if field not in fields:fields.append(field)
                emitted.extend(check_target(target))
                emitted.append(f'    fill_ready(page, {target}, {value}, {field!r})')
                action_kind='fill'
            elif re.match(r'(?:click|press|tap|submit)\b',low):
                role,label=extract_click(action)
                target=select_subject(label,raw,bundles,snapshot,role if role in {'link','menuitem'} else 'interaction' if role=='text' else 'button')
                if not target:requested_target=label;failures.append('missing_or_ambiguous_click_target');continue
                emitted.extend(check_target(target))
                emitted.append(f'    click_ready(page, {target}, {label!r})')
                action_kind='click'
            elif re.match(r'(?:select|choose|pick)\b',low):
                field,selected=extract_select(action)
                target=select_subject(field,raw,bundles,snapshot,'select')
                if not target:requested_target=field;failures.append('missing_or_ambiguous_select_target');continue
                emitted.append(f'    {target}.select_option(label={selected!r})')
                action_kind='select'
            elif re.match(r'(?:check|uncheck)\b',low) and not re.search(r'validity|checkValidity', expected, re.I):
                label=re.sub(r'^(?:check|uncheck)\s+(?:the\s+)?','',action,flags=re.I)
                target=select_subject(label,raw,bundles,snapshot,'checkbox')
                if not target:requested_target=label;failures.append('missing_or_ambiguous_checkbox_target');continue
                method='uncheck' if low.startswith('uncheck') else 'check'
                emitted.append(f'    {target}.{method}()')
                action_kind=method
            elif re.match(r'(?:verify|assert|ensure|confirm|validate|inspect|check)\b',low) and re.search(r'validity|checkValidity', expected, re.I):
                field_match=re.search(r'(?:the\s+)?([\w -]+?)\s+field',raw,re.I)
                field=re.sub(r'^(?:inspect|check|verify)\s+(?:the\s+)?','',field_match.group(1),flags=re.I) if field_match else ''
                target=select_subject(field,raw,bundles,snapshot,'input')
                if not target:requested_target=field;failures.append('missing_or_ambiguous_fill_target');continue
                action_kind='assert'
            elif re.match(r'(?:verify|assert|ensure|confirm|validate)\b',low):
                action_kind='assert'
            else:failures.append('unsupported_action')
        expectations=expectation_parts(expected or (raw if action_kind=='assert' else ''),fields)
        for expectation in expectations:
            spec=explicit_contract(expectation,raw,number)
            if spec:
                emitted.append(contract_line(spec));continue
            if 'heading' in expectation.lower() and re.search(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}',expectation):
                failures.append('unbound_environment_heading');unsupported.append(expectation);continue
            if re.search(r'within (?:the )?[\w -]+ field group',expectation,re.I):
                failures.append('unsupported_expected_outcome');unsupported.append(expectation);continue
            # An open menu is evidenced by a named, visible menu item in this
            # same outcome. No inferred expansion state is used on its own.
            if re.fullmatch(r'(?:the )?[\w -]+menu is open',expectation,re.I) and any(re.search(r'menu item.*visible',e,re.I) for e in expectations):
                continue
            validity_kind = ('value_missing' if re.search(r'\bvalidity\.valueMissing\b.*\btrue\b', expectation, re.I)
                             else 'invalid' if re.search(r'\bcheckValidity\(\).*\bfalse\b', expectation, re.I) else None)
            if validity_kind and target:
                emitted.append(contract_line({'version':1,'step':number,'kind':validity_kind,'subject':target,'scope':None,
                    'source':'manual_expected_result','expected_text':expectation,'action_text':raw}))
                continue
            if action_kind=='click' and re.fullmatch(r'[\w -]*required[\w -]*validation prevents submission\.?',expectation,re.I):
                pending_completion.append((number, True));continue
            if re.fullmatch(r'(?:the )?(?:page does not redirect|(?:user |page )?remains on (?:the )?[\w /-]+page)\.?',expectation,re.I) and last_navigation_binding:
                spec={'version':1,'step':number,'kind':'url_unchanged','reference_binding':last_navigation_binding,
                      'source':'manual_expected_result','expected_text':expectation,'action_text':raw}
                emitted.append(contract_line(spec));continue
            if action_kind=='click' and re.fullmatch(r'(?:the )?[\w -]*submission completes\.?',expectation,re.I):
                pending_completion.append((number, False));continue
            spec=outcome_contract(expectation,raw,snapshot,number)
            if spec:
                emitted.append(contract_line(spec));continue
            if action_kind=='fill' and value in {"''", '""'} and re.search(r'populated',expectation,re.I):
                failures.append('contradictory_expected_input_state');continue
            if action_kind=='fill' and target and value is not None and re.search(r'populated|entered value|supplied value|contains an empty string',expectation,re.I):
                emitted.append(f'    expect({target}).to_have_value({value}, timeout=ASSERTION_TIMEOUT_MS)')
                if re.search(r'mask',expectation,re.I):
                    emitted.append(f"    expect({target}).to_have_attribute('type', 'password', timeout=ASSERTION_TIMEOUT_MS)")
                continue
            if action_kind=='fill' and target and re.search(r'masks? (?:its |the )?display',expectation,re.I):
                emitted.append(f"    expect({target}).to_have_attribute('type', 'password', timeout=ASSERTION_TIMEOUT_MS)")
                continue
            translated=assertion_lines(expectation,action=raw,locator=target,value=value)
            if translated:
                emitted.extend(translated);continue
            # Navigation completion is represented by successful goto + rendered
            # document, but it never substitutes for a form/business assertion.
            if action_kind=='goto' and re.fullmatch(r'(?:the )?[\w /-]*page (?:loads|is loaded)\.?',expectation,re.I):
                emitted.append("    expect(page.locator('body')).to_be_visible()");continue
            failures.append('unsupported_expected_outcome')
            unsupported.append(expectation)
        if not expectations:failures.append('missing_expected_outcome')
        lines.extend(emitted)
        step_operations.append((number,list(emitted)))
        if failures:
            unresolved.append(number)
            lines.append(f'    pytest.skip("Untranslated step {number}: '+', '.join(dict.fromkeys(failures))+'")')
        step_records.append({'step':number,'action_kind':action_kind,'action_text':raw,'target':requested_target,'status':'partial' if failures else 'translated',
                             'reasons':list(dict.fromkeys(failures)), 'unsupported_outcomes':unsupported,
                             'expected_result':expected,
                             'url_asserted':any(re.search(r'expect\(page\)\.to_have_url\(',line) for line in emitted)})
        previous_expected.extend(expectations)
    for number, required_validation in pending_completion:
        record=next(r for r in step_records if r['step']==number)
        outcomes=[c['step'] for c in contracts if c['step']>number and (
                  c['kind'] in {'value_missing','invalid'} if required_validation else c['kind']=='visible'
                  and re.search(r'\b(?:message|error|success)\b',c['expected_text']+' '+c.get('action_text',''),re.I))]
        if outcomes:
            record['deferred_to_steps']=sorted(set(outcomes))
        else:
            record['status']='partial';record['reasons'].append('submission_outcome_not_supplied')
            unresolved.append(number);lines.append(f'    pytest.skip("Untranslated step {number}: submission_outcome_not_supplied")')
    overall=manual.get('expected_result','')
    overall_missing=[];overall_bindings=[]
    for item in expectation_parts(overall,fields):
        normalize=lambda t: ' '.join(words(t))
        if any(normalize(item)==normalize(previous) for previous in previous_expected):continue
        # Bind summary phrases to earlier executable business outcomes rather
        # than replaying an authenticated assertion after logout.
        summary=item
        summary=re.sub(r'^After [\w -]+,?\s*', '',summary,flags=re.I)
        combined=re.fullmatch(r'[\w -]+ displays (the heading .+?) at a URL containing (.+)',summary,re.I)
        items=[combined[1]+' is visible.', 'The URL contains '+combined[2]] if combined else [summary]
        bound=[]
        for part in items:
            spec=explicit_contract(part,'',len(step_records)+1)
            translated=assertion_lines(part)
            if spec:
                matches=[c for c in contracts if c['kind']==spec['kind'] and c.get('subject')==spec.get('subject') and c.get('expected_value')==spec.get('expected_value')]
                if matches:bound.extend(c['step'] for c in matches);continue
            if translated and all(any(line.strip()==old.strip() for old in lines) for line in translated):
                bound.extend(number for number,operations in step_operations if any(line.strip()==old.strip() for line in translated for old in operations));continue
            if normalize(part) in {normalize(p) for p in previous_expected}:bound.extend(r['step'] for r in step_records if r['status']=='translated');continue
            break
        else:
            if bound:
                overall_bindings.append({'summary':item,'steps':sorted(set(bound)),'proof_scope':'observable_ui'});continue
        spec=outcome_contract(item,'',snapshot,len(step_records)+1)
        if spec:lines.append(contract_line(spec))
        else:
            binding = summary_binding(item, contracts, step_records)
            if binding: overall_bindings.append(binding)
            else: overall_missing.append(item)
    if overall_missing:lines.append('    pytest.skip("Overall expected outcome lacks explicit executable evidence")')
    if not lines:lines=['    pytest.skip("No manual steps supplied")']
    script=('import os\nimport re\nimport pytest\nfrom playwright.sync_api import Page, expect\n'
            'from phoenix_shared.assertion_runtime import assert_contract, validate_target\n\n'
            f'def test_{test_name}(page: Page):\n'+'\n'.join(lines)+'\n')
    return {'script_code':script,'assertion_contracts':contracts,'step_contracts':step_records,
            'unresolved_steps':unresolved,'overall_outcome_unresolved':bool(overall_missing),
            'overall_bindings':overall_bindings,'unbound_overall_outcomes':overall_missing,
            'proposed_locator_targets':snapshot.proposals,
            'translation_targets':[r['target'] for r in step_records if r.get('target')]}
