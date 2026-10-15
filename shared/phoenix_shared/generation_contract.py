"""Generic explicit-outcome contracts and ordered artifact verification."""
from __future__ import annotations
import ast
import re
from html.parser import HTMLParser
from phoenix_shared.manual_semantics import negative_expectation, split_unquoted


class Snapshot(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.nodes=[]; self.stack=[]; self.proposals=[]; self.evidence={}
        self.feed(html or '')
    def handle_starttag(self,tag,attrs):
        node={'tag':tag,'attrs':dict(attrs),'text':'','parent':self.stack[-1] if self.stack else None}
        self.nodes.append(node)
        if tag not in {'input','br','img','hr','meta','link','source','area','wbr'}: self.stack.append(node)
    def handle_endtag(self,tag):
        for index in range(len(self.stack)-1,-1,-1):
            if self.stack[index]['tag']==tag:
                del self.stack[index:]; break
    def handle_data(self,data):
        for node in self.stack: node['text']+=' '+data
    def inside(self,node,parent):
        while node:
            if node is parent:return True
            node=node['parent']
        return False
    def form(self,label):
        wanted=set(words(label))-{'the','form','section'}
        candidates=[]
        for form in (n for n in self.nodes if n['tag']=='form'):
            buttons=[n for n in self.nodes if self.inside(n,form) and n['tag']=='button' and n['text'].strip()]
            matching=[b for b in buttons if wanted and wanted <= set(words(b['text']))]
            if len(matching)==1:
                button=' '.join(matching[0]['text'].split())
                candidates.append((form,f"page.locator('form').filter(has=page.get_by_role('button', name={button!r}, exact=True))"))
        return candidates[0] if len(candidates)==1 else (None,None)
    def scope(self,label):
        label=re.sub(r"`[^`]*`|'[^']*'|\"[^\"]*\"", '', label).lower()
        if 'form' in label:
            name=re.search(r'([\w-]+)\s+form',label)
            return self.form(name.group(1) if name else label)[1]
        for tag,role in [('header','banner'),('footer','contentinfo'),('main','main')]:
            if tag in label:
                nodes=[n for n in self.nodes if n['tag']==tag or n['attrs'].get('role')==role]
                return f"page.get_by_role({role!r})" if len(nodes)==1 else None
        if re.search(r'\b(?:anywhere|entire|whole)\b.*\bpage\b|\bon (?:the )?page\b',label):
            return "page.locator('body')" if any(n['tag']=='body' for n in self.nodes) else None
        return None


def words(text):
    text=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',str(text))
    return re.findall(r'[a-z0-9]+',text.lower())


def clauses(text):
    """Split punctuation/conjunctions outside supplied quotes; no dropped clauses."""
    parts=split_unquoted(r'(?<=[.!;])\s+|,\s*(?:and\s+)?(?=(?:the|a|an|user)\b|\w+\s+(?:is|are|remains|fails)\b)|\s+(?:and|followed by)\s+',text,flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def structured_text_expectation(text):
    """Recognize explicit tag/text prose so qualifiers never become UI text."""
    return bool(re.search(r"[`\"'][^`\"']+[`\"']\s+element\s+with\s+text\b",text,re.I))


def structured_text_contract(text,action,step):
    """Bind only an explicit native tag, exact text and native container tag.

    Unsupported structures remain unresolved; no current-page inference can
    substitute for a scope explicitly named for a later page.
    """
    import json
    match=re.fullmatch(
        r"(?:the\s+)?(?:central\s+)?(?P<q1>[`\"'])(?P<tag>h[1-6]|button|p|div|span|label|a)(?P=q1)"
        r"\s+element\s+with\s+text\s+(?P<q2>[`\"'])(?P<label>[^\r\n]+?)(?P=q2)"
        r"\s+is\s+visible\s+within\s+(?:the\s+)?(?P<q3>[`\"'])(?P<scope>main|header|footer|nav|section|article)(?P=q3)"
        r"(?:\s+content\s+area)?\.?",text.strip(),re.I)
    if not match:return None
    label=match['label']
    if not label.strip() or any(ord(c)<32 for c in label):return None
    scope=f"page.locator({match['scope'].lower()!r})"
    # Playwright :text-is provides exact normalized text matching on the
    # explicitly supplied native tag; multiple matches fail at runtime.
    selector=match['tag'].lower()+':text-is('+json.dumps(label,ensure_ascii=False)+')'
    return {'version':1,'step':step,'kind':'visible','subject':f"{scope}.locator({selector!r})",
            'scope':scope,'source':'manual_expected_result','expected_text':text.strip(),'action_text':action,
            'expected_exact_text':label}


def outcome_contract(expected,action,snapshot,step):
    """Return a contract only for explicit subject/state evidence."""
    text=expected.strip();low=text.lower()
    if structured_text_expectation(text):
        return structured_text_contract(text,action,step)
    scope=snapshot.scope(text)
    if re.search(r'within (?:the )?[\w -]+ field group',text,re.I):
        # A scoped repeated message cannot fall back to a global text query.
        # The evidence-aware compiler must bind its physical field group.
        return None
    values=[next(v for v in group if v) for group in re.findall(r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"",text)]
    negative=negative_expectation(text)
    if negative and not scope:scope=snapshot.scope(action)
    if negative and not scope and 'heading' in low:
        scope=snapshot.scope('anywhere on the page')
    if values and any(w in low for w in ('visible','displayed','shown','present','appears','absent')):
        if negative and not scope:return None
        kind='absent' if negative and any(w in low for w in ('present','absent')) else 'hidden' if negative else 'visible'
        root=scope or 'page'
        subject=f'{root}.get_by_role("heading", name={values[0]!r}, exact=True)' if 'heading' in low else f'{root}.get_by_text({values[0]!r}, exact={not negative!r})'
    elif 'form' in low and any(w in low for w in ('visible','available','displayed')):
        subject=snapshot.scope(text)
        if not subject:return None
        kind='visible';scope=None
    else:return None
    return {'version':1,'step':step,'kind':kind,'subject':subject,'scope':scope,
            'source':'manual_expected_result','expected_text':text,'action_text':action}


def workflow_summary_binding(text, contracts, records):
    """Bind recognized UI workflow prose to typed, already executed predicates."""
    translated={r['step']:r for r in records if r.get('status')=='translated'}
    cs=[c for c in contracts if c.get('step') in translated]
    positive=[c for c in cs if c.get('kind')=='record_present' and c.get('target_evidence') and c.get('expected_values')]
    saved=[c for c in cs if c.get('kind')=='data_visible' and c.get('expected_values')]
    def identity(values):
        # Preserve literals, variable order and multiplicity. Merely sharing
        # environment names does not establish that the same record was found.
        if not isinstance(values,list) or not values or any(not isinstance(v,str) or not v.strip() for v in values):
            return None
        return ' '.join(' '.join(v.split()) for v in values)
    creation=[(a,b) for a in saved for b in positive if a['step']<b['step']
              and identity(a['expected_values']) and identity(a['expected_values'])==identity(b['expected_values'])
              and translated[a['step']].get('url_asserted')
              and translated[a['step']].get('action_kind')=='click'
              and re.search(r'\b(?:save|create|add|submit|register|apply|confirm)\b',translated[a['step']].get('action_text',''),re.I)]
    def result(steps,scope='observable_ui'):
        return {'summary':text,'steps':sorted(set(steps)),'proof_scope':scope}
    plain=text.strip().rstrip('.,')
    # Shared input conditions are preserved as one sentence, rather than split
    # at field-list conjunctions and treated as independent business outcomes.
    condition=re.fullmatch(r'(?:A|The) record is successfully created and searchable when (.+?) are supplied and (.+?) is omitted\.?',plain,re.I)
    if condition and creation:
        inputs={k:v for r in translated.values() for k,v in r.get('input_values',{}).items()}
        requested=[x.strip() for x in re.split(r',\s*(?:and\s+)?|\s+and\s+',condition[1],flags=re.I)]
        matched=lambda label:next((v for k,v in inputs.items() if ' '.join(words(k))==' '.join(words(label))),None)
        values=[matched(label) for label in requested]
        if values and all(v for v in values) and matched(condition[2])=='':
            pairs=[(a,b) for a,b in creation if identity(values)==identity(a['expected_values'])]
            if pairs:return result([c['step'] for pair in pairs for c in pair],'observable_saved_and_filtered_record')
        return None
    blocked=re.fullmatch(r'(?:The )?form blocks submission when required (?:fields|names) are empty\.?',plain,re.I)
    if blocked:
        proof=[c for c in cs if c.get('kind')=='no_new_records']
        errors=[c for c in cs if c.get('kind')=='field_messages' and any(p['step']==c['step'] for p in proof)]
        if proof and errors:return result([c['step'] for c in proof+errors],'configured_record_comparison_and_field_validation')
        return None
    pieces=[v.strip() for v in re.split(r',\s*(?:and\s+)?',plain) if v.strip()]
    steps=[]
    for piece in pieces:
        if re.fullmatch(r'(?:(?:The )?(?:user|administrator|operator|customer) )?logs in(?: successfully)?',piece,re.I):
            matches=[r for r in translated.values() if r.get('url_asserted') and
                     re.search(r'\b(?:login|log in|sign in)\b',r.get('action_text',''),re.I) and
                     any(c['step']==r['step'] and c.get('kind')=='visible' for c in cs)]
            if not matches:return None
            steps.extend(r['step'] for r in matches)
        elif re.fullmatch(r'creates (?:a|an|the) [\w -]+',piece,re.I):
            if not creation:return None
            entity=re.sub(r'^creates (?:a|an|the) ', '',piece,flags=re.I)
            matches=[pair for pair in creation if set(words(entity))<=set(words(pair[1].get('expected_text','')))]
            if not matches:return None
            steps.extend(c['step'] for pair in matches for c in pair)
        elif re.fullmatch(r'finds (?:that|the) [\w -]+ in (?:the )?list',piece,re.I):
            entity=re.sub(r'^finds (?:that|the) | in (?:the )?list$', '',piece,flags=re.I)
            matches=[c for c in positive if set(words(entity))<=set(words(c.get('expected_text',''))) and translated[c['step']].get('action_kind')=='search']
            if not matches:return None
            steps.extend(c['step'] for c in matches)
        elif re.fullmatch(r'logs out(?: successfully)?',piece,re.I):
            matches=[r for r in translated.values() if r.get('url_asserted') and
                     re.search(r'\b(?:logout|log out|sign out)\b',r.get('action_text',''),re.I) and
                     any(c['step']==r['step'] and c.get('kind')=='absent' and c.get('scope') for c in cs) and
                     any(c['step']==r['step'] and c.get('kind')=='visible' for c in cs)]
            if not matches:return None
            steps.extend(r['step'] for r in matches)
        else:return None
    return result(steps) if steps else None


def summary_binding(text, contracts, records):
    """Bind narrative summaries to explicit outcomes, never invent a UI subject.

    Logged-out summaries here describe the observable UI only. They cannot
    establish server-side session invalidation or cookie/token absence.
    """
    workflow=workflow_summary_binding(text,contracts,records)
    if workflow:return workflow
    normalized = ' '.join(words(text))
    displayed=re.fullmatch(r'.+? displays? (?:an? )?(.+?) (?:error|message)\.?',text,re.I)
    if displayed:
        message=set(words(displayed[1]))
        candidates=[c for c in contracts if c['kind']=='visible' and message<=set(words(c.get('expected_text','')))]
        if candidates:return {'summary':text,'steps':sorted({c['step'] for c in candidates}),'proof_scope':'observable_ui'}
    empty_submission=re.fullmatch(r'Submitting .+? fields empty displays field.level validation errors\.?',text,re.I)
    if empty_submission:
        candidates=[c for c in contracts if c['kind'] in {'count','field_messages'} and c.get('expected_count',0)>0 and 'validation' in c.get('expected_text','').lower()]
        empty_fills=[r for r in records if r.get('status')=='translated' and re.search(r'\bclear\b',r.get('action_text',''),re.I)]
        if candidates and empty_fills:return {'summary':text,'steps':sorted({c['step'] for c in candidates}|{r['step'] for r in empty_fills}),'proof_scope':'observable_validation_messages'}
    never=re.fullmatch(r'Neither attempt opens (?:the )?(.+?)\.?',text,re.I)
    if never:
        label=set(words(never[1]))
        candidates=[c for c in contracts if c['kind'] in {'absent','hidden'} and label<=set(words(c.get('expected_text',''))) and c.get('scope')]
        if len({c['step'] for c in candidates})==2:return {'summary':text,'steps':sorted({c['step'] for c in candidates}),'proof_scope':'observable_ui'}
    negative = [c for c in contracts if c['kind'] in {'hidden', 'absent'} and c.get('scope')
                and re.search(r'\b(?:authenticated|authentication|account|signed|logged)\b',
                              c['action_text'] + ' ' + c['expected_text'], re.I)]
    errors = [c for c in contracts if c['kind'] in {'visible','count'}
              and re.search(r'\b(?:error|rejection|rejected|denied|failure|validation)\b',
                            c['action_text'] + ' ' + c['expected_text'], re.I)]
    invalid = [c for c in contracts if c['kind'] in {'value_missing', 'invalid'}]
    completions = [r for r in records if r.get('deferred_to_steps')]
    forms = [c for c in contracts if c['kind'] == 'visible'
             and re.search(r'\bform\b', c['action_text'] + ' ' + c['expected_text'], re.I)]
    proof = []
    transition=re.fullmatch(r'([\w ]+?) (?:reaches|returns to) (?:the )?([\w ]+?) url',normalized)
    configured_heading=re.fullmatch(r'(?:displays?|shows?) (?:the )?configured ([\w ]+) heading',normalized)
    if transition:
        action_words=set(words(transition[1]));destination_words=set(words(transition[2]))-{'configured','the'}
        matched=[r for r in records if r.get('status')=='translated' and r.get('action_kind')=='click' and r.get('url_asserted')
                 and action_words<=set(words(r.get('action_text',''))) and destination_words<=set(words(r.get('expected_result','')))]
        if len(matched)==1:return {'summary':text,'steps':[matched[0]['step']],'proof_scope':'observable_ui'}
        return None
    if configured_heading:
        label=set(words(configured_heading[1]))
        proof=[c for c in contracts if c['kind']=='visible' and c.get('expected_heading_reference')
               and label<=set(words(c['expected_heading_reference']))]
        return {'summary':text,'steps':sorted({c['step'] for c in proof}),'proof_scope':'observable_ui'} if proof else None
    quoted_summary = [next(v for v in group if v) for group in
                      re.findall(r'`([^`]+)`|\'([^\']+)\'|"([^"]+)"', text)]
    if quoted_summary and re.search(r'\b(?:error|rejection|failure)\b', normalized):
        proof = [c for c in errors if any(q.casefold() in c['expected_text'].casefold() for q in quoted_summary)]
        if proof:
            return {'summary':text,'steps':sorted({c['step'] for c in proof}),'proof_scope':'observable_ui'}
    if re.search(r'\b(?:error|rejection|failure)\b', normalized):
        def message_core(contract):
            core = re.sub(r'\s+(?:error|message)?\s*(?:is|are)?\s+(?:visible|displayed|shown)\.?$', '', contract['expected_text'], flags=re.I)
            return re.sub(r'^(?:an?|the)\s+', '', core.strip(), flags=re.I).strip('`\'\" ').casefold()
        proof = [c for c in errors if message_core(c) and message_core(c) in text.casefold()]
        if proof:
            return {'summary':text,'steps':sorted({c['step'] for c in proof}),'proof_scope':'observable_ui'}
    if re.fullmatch(r'(?:the )?[\w ]*(?:error|rejection|failure) (?:is )?(?:displayed|visible|shown)', normalized):
        wanted = set(words(text)) - {'the','is','displayed','visible','shown'}
        proof = [c for c in errors if wanted <= set(words(c['action_text'] + ' ' + c['expected_text']))]
    elif re.search(r'\bvalidation errors?\b', normalized):
        proof = [c for c in errors if c['kind'] in {'visible','count'}
                 and re.search(r'\bvalidation message\b', c['expected_text'], re.I)
                 and re.match(r'\s*(?:click|press|tap|submit)\b', c['action_text'], re.I)]
    elif re.match(r'(?:neither|none)\b', normalized) and re.search(r'\b(?:opens?|reaches?|shows?)\b', normalized):
        wanted = set(words(text)) - {'neither','none','attempt','attempts','opens','open','reaches','reach','shows','show','the','a','an'}
        proof = [c for c in contracts if c['kind'] in {'hidden','absent'}
                 and wanted & set(words(c['expected_text']))]
    elif re.fullmatch(r'(?:the )?[\w ]*(?:is |are )?(?:rejected|denied)', normalized):
        # Rejection requires an explicit rejected-input action and its submitted
        # error outcome. A random visible message or absent header is not enough.
        subject=set(words(text))-{'the','is','are','rejected','denied','supplied','incorrect','invalid'}
        fills=[r for r in records if r.get('action_kind')=='fill' and subject <= set(words(r.get('action_text','')))]
        if completions and errors and fills:
            proof = errors
    elif re.fullmatch(r'(?:the )?(?:user|account) (?:remains|is) (?:logged|signed) out', normalized):
        if negative and forms and (errors or invalid):
            proof = negative + forms + (errors or invalid)
    elif re.fullmatch(r'(?:the )?[\w ]*fails required field validation', normalized):
        subject = set(words(text)) - {'the','empty','field','fails','required','validation'}
        proof = [c for c in invalid if subject and subject <= set(words(c['action_text']))]
    elif re.fullmatch(r'(?:the )?submission is (?:prevented|blocked)', normalized):
        if completions and invalid:
            proof = invalid
    return {'summary':text, 'steps':sorted({c['step'] for c in proof}), 'proof_scope':'observable_ui'} if proof else None


def operation_signature(code, *, preserve_selectors=False):
    """Ordered actions/data/assertions; helper bodies do not count as test work."""
    tree=ast.parse(code); events=[]
    class Canonical(ast.NodeTransformer):
        def visit_Attribute(self,node):
            if isinstance(node.value,ast.Name) and node.value.id=='self' and node.attr in {'_page','page'}:
                return ast.Name(id='page',ctx=ast.Load())
            return self.generic_visit(node)
    class Walker(ast.NodeVisitor):
        def visit_FunctionDef(self,node):
            if node.name in {'configure_page','unique_visible','dismiss_known_overlays','expect_url_path'} or node.name.endswith('_ready'):
                return
            for statement in node.body:self.visit(statement)
        visit_AsyncFunctionDef=visit_FunctionDef
        def visit_Assert(self,node):
            events.append(('assert',ast.unparse(Canonical().visit(node))))
        def visit_Call(self,node):
            name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
            if name in {'fill_ready','click_ready','select_autocomplete_option'}:
                # Locator replacement may change strategy while preserving target.
                # The immutable target description and supplied value remain checked.
                events.append((name,ast.unparse(Canonical().visit(node)) if preserve_selectors else tuple(ast.unparse(a) for a in node.args[2:])))
                return
            if name in {'assert_contract','validate_target','read_record_identities'}:
                events.append((name,ast.unparse(node.args[1]) + repr([(k.arg,ast.unparse(k.value)) for k in node.keywords]) if len(node.args)>1 else 'missing'));return
            if name in {'goto','fill','click','select_option','check','uncheck','press','set_input_files'} or name.startswith(('to_','not_to_')):
                if name=='to_be_visible' and "locator('body')" in ast.unparse(node):return
                events.append((name,ast.unparse(Canonical().visit(node)) if preserve_selectors or not name.startswith(('to_', 'not_to_')) else tuple([*(ast.unparse(a) for a in node.args), *(str(k.arg)+'='+ast.unparse(k.value) for k in node.keywords)])));return
            self.generic_visit(node)
    Walker().visit(tree)
    return events


def artifact_plan_issues(test):
    plan=test.get('generation_plan')
    if not isinstance(plan,dict):return []  # Older clients remain supported.
    expected=plan.get('operations',[])
    expected=[tuple([e[0],tuple(e[1]) if isinstance(e[1],list) else e[1]]) for e in expected]
    issues=[]
    if operation_signature(test.get('script_code') or '')!=expected:
        issues.append('flat: generated action/assertion order or data differs from the generation plan')
    pom=test.get('pom_bundle')
    if pom:
        observed=[]
        expanded=None
        if pom.get('architecture')=='page_state':
            from phoenix_shared.page_objects import expanded_pom_script
            try:expanded=expanded_pom_script(pom)
            except (ValueError,KeyError,SyntaxError) as exc:
                issues.append('POM: invalid test-to-method call graph: '+str(exc))
            if expanded is not None:observed=operation_signature(expanded)
        else:
            for node in pom.get('page_objects',[]):observed.extend(operation_signature(node.get('code','')))
        if observed!=expected:issues.append('POM: generated action/assertion order or data differs from the generation plan')
        exact=[]
        if expanded is not None:exact=operation_signature(expanded,preserve_selectors=True)
        else:
            for node in pom.get('page_objects',[]):exact.extend(operation_signature(node.get('code',''), preserve_selectors=True))
        if exact!=operation_signature(test.get('script_code') or '', preserve_selectors=True):
            issues.append('POM: executable selectors or assertions differ from the flat generation artifact')
    return issues
