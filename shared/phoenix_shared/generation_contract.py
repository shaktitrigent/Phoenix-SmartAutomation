"""Generic explicit-outcome contracts and ordered artifact verification."""
from __future__ import annotations
import ast
import re
from html.parser import HTMLParser
from phoenix_shared.manual_semantics import negative_expectation


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
    quoted=re.compile(r"`[^`]*`|'[^']*'|\"[^\"]*\"")
    saved=[]
    def hide(match):saved.append(match.group());return f'QUOTEDTOKEN{len(saved)-1}X'
    hidden=quoted.sub(hide,str(text or ''))
    parts=re.split(r'(?<=[.!;])\s+|,\s*(?:and\s+)?(?=(?:the|a|an|user)\b|\w+\s+(?:is|are|remains|fails)\b)|\s+(?:and|followed by)\s+',hidden,flags=re.I)
    return [re.sub(r'QUOTEDTOKEN(\d+)X',lambda m:saved[int(m.group(1))],p).strip() for p in parts if p.strip()]


def outcome_contract(expected,action,snapshot,step):
    """Return a contract only for explicit subject/state evidence."""
    text=expected.strip();low=text.lower();scope=snapshot.scope(text)
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


def summary_binding(text, contracts, records):
    """Bind narrative summaries to explicit outcomes, never invent a UI subject.

    Logged-out summaries here describe the observable UI only. They cannot
    establish server-side session invalidation or cookie/token absence.
    """
    normalized = ' '.join(words(text))
    negative = [c for c in contracts if c['kind'] in {'hidden', 'absent'} and c.get('scope')
                and re.search(r'\b(?:authenticated|authentication|account|signed|logged)\b',
                              c['action_text'] + ' ' + c['expected_text'], re.I)]
    errors = [c for c in contracts if c['kind'] == 'visible'
              and re.search(r'\b(?:error|rejection|rejected|denied|failure)\b',
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
    if re.fullmatch(r'(?:the )?[\w ]*(?:error|rejection|failure) (?:is )?(?:displayed|visible|shown)', normalized):
        wanted = set(words(text)) - {'the','is','displayed','visible','shown'}
        proof = [c for c in errors if wanted <= set(words(c['action_text'] + ' ' + c['expected_text']))]
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
        def visit_Call(self,node):
            name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
            if name in {'fill_ready','click_ready'}:
                # Locator replacement may change strategy while preserving target.
                # The immutable target description and supplied value remain checked.
                events.append((name,ast.unparse(Canonical().visit(node)) if preserve_selectors else tuple(ast.unparse(a) for a in node.args[2:])))
                return
            if name in {'assert_contract','validate_target'}:
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
        for node in pom.get('page_objects',[]):observed.extend(operation_signature(node.get('code','')))
        if observed!=expected:issues.append('POM: generated action/assertion order or data differs from the generation plan')
        exact=[]
        for node in pom.get('page_objects',[]):exact.extend(operation_signature(node.get('code',''), preserve_selectors=True))
        if exact!=operation_signature(test.get('script_code') or '', preserve_selectors=True):
            issues.append('POM: executable selectors or assertions differ from the flat generation artifact')
    return issues
