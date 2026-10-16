"""State-preserving scanning, scoped capture and target-aware validation.

One owned browser per operation; injected pages are never navigated or closed.
Selector expressions are interpreted with a small AST allow-list, never eval.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from phoenix_shared.models.locator import Locator, LocatorStrategy


def locator_on_page(page: Any, candidate: Locator):
    if not isinstance(candidate.value,str) or not candidate.value.strip():
        raise ValueError("Empty selectors are not target evidence")
    from phoenix.locators.smartlocator_fallback import has_positional_selector
    if has_positional_selector(candidate.value):
        raise ValueError("Positional selectors are not identity evidence")
    from phoenix_shared.assertion_runtime import resolve_subject
    return resolve_subject(page, candidate.to_playwright())



_DESCRIBE = r"""(element, policy) => {
 const clean = value => (value || '').replace(/\s+/g, ' ').trim();
 const slots = policy ? policy.mutable_text_selectors.flatMap(s => [...element.querySelectorAll(s)]) : [];
 if (policy && (slots.length !== policy.mutable_text_selectors.length || new Set(slots).size !== slots.length ||
     slots.some(n => n.children.length || n.matches('input,button,a,select,textarea,[role],[tabindex]'))))
   throw new Error('Mutable display slots must be distinct noninteractive text leaves');
 const snapshotText = node => {
   if (!node) return '';
   const texts=[];
   const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);
   for(let n=walker.nextNode();n;n=walker.nextNode()) {
     if (n.parentElement?.closest('script,style,template')) continue;
     if (slots.includes(n.parentElement)) { texts.push('[mutable-display]'); continue; }
     const value=clean(n.nodeValue);if(value)texts.push(value);
   }
   return texts.join(' ');
 };
 const attrs = node => Object.fromEntries([
   ...['id','class','name','type','role','placeholder','aria-label','href'].map(k => [k,node.getAttribute(k)||'']),
   ...[...node.attributes].filter(a=>a.name.startsWith('data-')).map(a=>[a.name,a.value])]);
 const sectionHeading = node => {
   const own = [...node.children].find(n => /^H[1-6]$/.test(n.tagName));
   const preceding = node.previousElementSibling;
   return snapshotText(own || (/^H[1-6]$/.test(preceding?.tagName || '') ? preceding : null));
 };
 // Form identity excludes entered values and validation-message text.
 // Capture it only after ordinary identity has been independently accepted.
 const form = element.closest('form');
 const formAttrs = node => Object.fromEntries(['id','name','action','method','role','data-testid','data-test','data-cy']
   .map(k=>[k,node.getAttribute(k)||'']));
 const formControl = node => ({tag:node.tagName.toLowerCase(),
   ...Object.fromEntries(['id','name','type','role','placeholder','aria-label','href','data-testid','data-test','data-cy']
     .map(k=>[k,node.getAttribute(k)||''])),
   label:[...(node.labels||[])].map(n=>snapshotText(n)).join(' '),
   text:node.matches('input,textarea,select') ?
     (node.matches('input[type=submit],input[type=button],input[type=reset]') ? clean(node.value) : '') : snapshotText(node)});
 const controls = form ? [...form.querySelectorAll('input,textarea,select,button,a[href],[role=button],[role=checkbox],[role=radio],[role=combobox],[role=textbox]')]
   .filter(n=>n.closest('form')===form).map(formControl) : [];
 let scopeAnchor=null;
 for(let p=form?.parentElement,i=0;p && i<8;p=p.parentElement,i++) {
   if(p.id || p.getAttribute('data-testid') || p.getAttribute('data-test')) {
     scopeAnchor={tag:p.tagName.toLowerCase(),id:p.id||'',
       'data-testid':p.getAttribute('data-testid')||'','data-test':p.getAttribute('data-test')||''};break;
   }
 }
 const form_identity = form && ![...form.elements].some(n=>!form.contains(n)) ?
   {version:1,source:'validated_live_form_controls',form:formAttrs(form),controls,scope_anchor:scopeAnchor} : null;
 const ancestors=[];
 for(let p=element.parentElement, i=0; p && i<8; p=p.parentElement,i++)
   ancestors.push({tag:p.tagName.toLowerCase(), ...attrs(p), heading:sectionHeading(p), text:snapshotText(p).slice(0,1500)});
 const cell=element.closest('td,th'), table=element.closest('table');
 const column=cell ? [...cell.parentElement.children].indexOf(cell) : -1;
 const table_context=table ? {table_id:table.id,table_testid:table.getAttribute('data-testid')||table.getAttribute('data-test')||'',column_header:snapshotText(table.querySelector('thead tr')?.children[column])} : {};
 const structure = node => ({tag:node.tagName.toLowerCase(),attributes:attrs(node),
   text:slots.includes(node) ? '[mutable-display]' : [...node.childNodes].filter(n=>n.nodeType===3).map(n=>clean(n.nodeValue)).filter(Boolean).join(' '),
   children:[...node.children].map(structure)});
 const column_headers=element.matches('table,[role=table],[role=grid]') ?
   [...element.querySelectorAll('th,[role=columnheader]')].map(n=>clean(n.textContent)).filter(Boolean) : [];
 return {tag:element.tagName.toLowerCase(), ...attrs(element), table_context, column_headers, form_identity,
         ...(policy ? {content_structure:structure(element), mutable_display_values:slots.map(n=>clean(n.textContent))} : {}),
         text:element.matches('input') ? (['submit','button','reset'].includes(element.type) ? clean(element.value) : '') : snapshotText(element),
         siblings:[...(element.parentElement?.children||[])].filter(n=>n!==element).slice(0,4).map(n=>({tag:n.tagName.toLowerCase(),...attrs(n),text:snapshotText(n).slice(0,300)})),
         ancestors};
}"""


def valid_form_control_identity(profile):
    """Accept only a complete, value-free captured native form description."""
    if not isinstance(profile, dict) or set(profile) != {'version','source','form','controls','scope_anchor'}:
        return False
    if profile['version'] != 1 or profile['source'] != 'validated_live_form_controls':
        return False
    form_keys={'id','name','action','method','role','data-testid','data-test','data-cy'}
    if not isinstance(profile['form'],dict) or set(profile['form']) != form_keys or not all(isinstance(v,str) for v in profile['form'].values()):
        return False
    anchor=profile['scope_anchor']
    if anchor is not None and (not isinstance(anchor,dict) or set(anchor)!={'tag','id','data-testid','data-test'} or
            not all(isinstance(v,str) for v in anchor.values()) or not any(anchor[k] for k in ('id','data-testid','data-test'))):
        return False
    keys={'tag','id','name','type','role','placeholder','aria-label','href','data-testid','data-test','data-cy','label','text'}
    controls=profile['controls']
    if not isinstance(controls,list) or len(controls)<2 or len(controls)>100:
        return False
    for control in controls:
        if not isinstance(control,dict) or set(control)!=keys or not all(isinstance(v,str) for v in control.values()):
            return False
        if control['tag'] in {'input','textarea','select'} and control['text'] and not (control['tag']=='input' and control['type'] in {'button','submit','reset'}):
            return False
        if not any(control[k] for k in ('id','name','placeholder','aria-label','href','data-testid','data-test','data-cy','label','text')):
            return False
    return True


def identity_matches(actual: dict, expected: dict) -> bool:
    """Require explicit element evidence and any captured container distinction."""
    attrs = expected.get("attributes") or {}
    data = {**attrs, **expected}
    content = data.get('content_identity')
    if content:
        if content.get('version') != 1 or not content.get('mutable_text_selectors') or not content.get('structure'):
            return False
        if actual.get('content_structure') != content['structure']:
            return False
        # Only explicitly declared display leaves are masked. The descriptor still
        # checks all other text, attributes and physical ancestor distinctions.
        data = {**data, 'text':content['text'], 'ancestor_context':content['ancestor_context']}
        if str(actual.get('class', '')) != str(data.get('class', '')):
            return False
    checks = {k: str(data[k]) for k in
              ("tag", "id", "name", "type", "role", "placeholder", "aria-label", "data-testid", "data-test", "href")
              if data.get(k)}
    nested_data = data.get("data") or {}
    for k in nested_data:
        if k.startswith("data-") and nested_data.get(k):
            checks[k] = str(nested_data[k])
    text = " ".join(str(data.get("text") or data.get("visible_text") or "").split())
    if text:
        checks["text"] = text
    # A tag alone cannot establish which physical control was requested.
    context = data.get("ancestor_context") or {}
    contextual_identity = bool(context.get('container_id') or context.get('container_test_id') or
                               context.get('container_testid') or context.get('distinguishing_text'))
    headers=data.get('column_headers') or []
    if headers and actual.get('column_headers')!=headers:return False
    if not any(k != "tag" for k in checks) and not contextual_identity and not headers:
        return False
    if any(str(actual.get(k, "")) != v for k, v in checks.items()):
        return False
    context = data.get("ancestor_context") or {}
    form_identity = data.get('form_control_identity')
    if form_identity is not None:
        if content or context.get('container_tag') != 'form' or not valid_form_control_identity(form_identity):
            return False
        if actual.get('form_identity') != form_identity:
            return False
        # A complete captured control signature replaces only incidental form
        # text. Target attributes, labels, scope and live uniqueness still apply.
        context = {**context, 'container_text':'', 'distinguishing_text':''}
    row=context.get("row_context") or {}
    if isinstance(row,dict) and any(row.get(k) and str(actual.get("table_context",{}).get(k,""))!=str(row[k])
        for k in ("table_id","table_testid","column_header")):
        return False
    section=context.get("section_context") or {}
    if isinstance(section,dict):
        wanted={dest:str(section[src]) for src,dest in (("section_tag","tag"),("section_id","id"),("section_test_id","data-testid"),("section_heading","heading")) if section.get(src)}
        classes=set(str(section.get("section_class") or "").split())
        if (wanted or classes) and not any(all(str(a.get(k,""))==v for k,v in wanted.items())
                and classes <= set(str(a.get("class") or "").split()) for a in actual.get("ancestors",[])):
            return False
    context_checks = {}
    if context.get("container_tag"):
        context_checks["tag"] = str(context["container_tag"])
    for source, target in (("container_id", "id"), ("container_test_id", "data-testid"),
                           ("container_testid", "data-testid")):
        if context.get(source):
            context_checks[target] = str(context[source])
    distinction = context.get("distinguishing_text") or (None if form_identity is not None else data.get("distinguishing_text"))
    container_text = context.get("container_text")
    container_classes = set(str(context.get("container_class") or "").split())
    if context_checks or distinction or container_classes or container_text:
        return any(all(str(a.get(k, "")) == v for k,v in context_checks.items()) and
                   container_classes <= set(str(a.get("class") or "").split()) and
                   (not container_text or " ".join(str(container_text).split()).casefold() in str(a.get("text", "")).casefold() or (context.get("container_text_truncated") is True and str(container_text).casefold() == (str(a.get("text", ""))[:47] + "...").casefold())) and
                   (not distinction or str(distinction).casefold() in str(a.get("text", "")).casefold())
                   for a in actual.get("ancestors", []))
    return True


def observed_click_paths(page):
    """Snapshot paths for visible nodes with actual browser click handlers."""
    session = None
    try:
        session = page.context.new_cdp_session(page)
        obj = session.send("Runtime.evaluate", {"expression": "document.body", "objectGroup": "phoenix-click-capture"})["result"]["objectId"]
        listeners = session.send("DOMDebugger.getEventListeners", {"objectId": obj, "depth": -1})["listeners"]
        paths = []
        for identifier in dict.fromkeys(l.get("backendNodeId") for l in listeners if l.get("type") == "click"):
            if not identifier or len(paths) >= 200: continue
            node = session.send("DOM.resolveNode", {"backendNodeId": identifier, "objectGroup": "phoenix-click-capture"})["object"]["objectId"]
            result = session.send("Runtime.callFunctionOn", {"objectId": node, "returnByValue": True,
                "functionDeclaration": """function() {
                    if (!this.getClientRects?.().length || ['HTML','BODY'].includes(this.tagName)) return null;
                    const parts=[];
                    for (let n=this; n?.nodeType===1; n=n.parentElement) {
                        const peers=[...(n.parentElement?.children || [])].filter(p=>p.tagName===n.tagName);
                        parts.unshift(n.tagName.toLowerCase()+(n.parentElement ? ':nth-of-type('+(peers.indexOf(n)+1)+')' : ''));
                    }
                    return parts.join(' > ');
                }"""})
            path = result.get("result", {}).get("value")
            if path: paths.append(path)
        return paths
    except Exception:
        # Other browser engines cannot claim listener evidence from Chromium CDP.
        return []
    finally:
        if session is not None:
            try: session.send("Runtime.releaseObjectGroup", {"objectGroup": "phoenix-click-capture"})
            finally: session.detach()


class LiveLocatorSession:
    def __init__(self, page, *, state_name="global", stability_threshold=0.8):
        self.page = page
        self.state_name = state_name
        self.stability_threshold = stability_threshold

    def wait_for_ready(self):
        self.page.wait_for_load_state("networkidle", timeout=30000)
        self.page.wait_for_function("""() => {
            if (!window.__phoenixScanReadiness) {
                const state = {changed: performance.now()};
                new MutationObserver(() => state.changed = performance.now())
                    .observe(document, {subtree:true, childList:true, attributes:true, characterData:true});
                window.__phoenixScanReadiness = state;
            }
            const busy = [...document.querySelectorAll('[aria-busy="true"], [role="progressbar"]')]
                .some(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden');
            return document.readyState === 'complete' && !busy &&
                performance.now() - window.__phoenixScanReadiness.changed >= 500;
        }""", timeout=30000)

    def generation_snapshot(self):
        """Capture the established state, omitting entered values and executable nodes."""
        return self.page.evaluate("""() => {
            const body=document.body.cloneNode(true);
            body.querySelectorAll('script,style,iframe').forEach(n=>n.remove());
            body.querySelectorAll('input,textarea').forEach(n=>{n.removeAttribute('value');if(n.tagName==='TEXTAREA')n.textContent='';});
            body.querySelectorAll('*').forEach(n=>[...n.attributes].filter(a=>a.name.startsWith('on')).forEach(a=>n.removeAttribute(a.name)));
            return body.outerHTML.slice(0,50000);
        }""")

    def validate(self, candidate, payload):
        try:
            target = locator_on_page(self.page, candidate)
            count = target.count()
            expected = payload.get("element_data") or {}
            policy = expected.get('content_identity')
            actual = target.evaluate(_DESCRIBE, policy) if count == 1 else {}
            identity = count == 1 and identity_matches(actual, expected)
            anchor_count=None;identity_count=None
            if identity:
                tag=str(expected.get("tag") or "")
                anchor_selector=tag if re.fullmatch(r"[a-z][a-z0-9-]*", tag) else "button,input,a,select,textarea,[role]"
                # Every possible identity match must satisfy its declared role.
                # Filtering by that requirement preserves duplicate detection
                # without exhausting the budget on unrelated layout nodes.
                role=str(expected.get("role") or "")
                if tag and re.fullmatch(r"[a-z][a-z0-9-]*",tag) and re.fullmatch(r"[a-z][a-z0-9-]*",role):
                    anchor_selector=tag+'[role='+json.dumps(role)+']'
                anchors=self.page.locator(anchor_selector)
                def matches(node):
                    try: return identity_matches(node.evaluate(_DESCRIBE, policy), expected)
                    except Exception: return False
                anchor_count=anchors.count()
                identity_count=sum(matches(n) for n in anchors.all()) if anchor_count<=500 else None
                identity=identity_count==1
            return {"match_count": count, "identity_matches": identity,
                    "anchor_count":anchor_count,"identity_count":identity_count,
                    "validation_reason":None if identity else "anchor_budget_exceeded" if anchor_count is not None and anchor_count>500 else "ambiguous_identity" if identity_count is not None and identity_count>1 else "identity_mismatch",
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                    "validation_url": self.page.url, "state_name": self.state_name}
        except Exception as exc:
            reason = ("unsupported_locator_expression" if isinstance(exc, ValueError) else
                      "invalid_selector" if re.search(r'Unexpected token|not a valid selector|parsing selector|Unknown engine', str(exc), re.I)
                      else "browser_validation_error")
            return {"match_count": None, "identity_matches": False,
                    "error": type(exc).__name__, "validation_reason": reason, "validation_url": self.page.url,
                    "state_name": self.state_name}

    def revalidate(self, bundles):
        self.wait_for_ready()
        from phoenix_shared.locator_policy import locator_accepted
        result=[]
        for bundle in bundles:
            meta=dict(bundle.metadata or {})
            # Recover selector-local provenance from old serialized raw records.
            # This repairs merged category lists, but grants no live acceptance:
            # every recovered candidate is validated below on this Page.
            from phoenix.locators.smartlocator_adaptor import convert_locators, CANDIDATE_EVIDENCE_KEYS
            recovered = {}
            raw_records = meta.get("smartlocator_raw_records") or []
            if raw_records:
                for rebuilt in convert_locators(raw_records, page=bundle.page):
                    if meta.get("element_identity") and rebuilt.metadata.get("element_identity") != meta["element_identity"]:
                        continue
                    for item in [rebuilt.primary, *rebuilt.alternates]:
                        recovered[(item.strategy.value, item.value)] = item
            expected=meta.get("element_data") or next((r.get("element_data") for r in
                meta.get("smartlocator_raw_records", []) if r.get("element_data")), {})
            validated=[]
            for candidate in [bundle.primary,*bundle.alternates]:
                restored = recovered.get((candidate.strategy.value, candidate.value))
                if restored is not None and (candidate.metadata or {}).get("source") != "locator_expert":
                    candidate_meta = dict(candidate.metadata or {})
                    for key in CANDIDATE_EVIDENCE_KEYS:
                        candidate_meta.pop(key, None)
                        if key in restored.metadata:
                            candidate_meta[key] = restored.metadata[key]
                    candidate = candidate.model_copy(update={"metadata": candidate_meta,
                        "confidence": restored.confidence, "verified_in_snapshot": None})
                outcome=self.validate(candidate, {"element_data":expected})
                cm={**(candidate.metadata or {}), **outcome}
                validated.append(candidate.model_copy(update={"metadata":cm,
                    "verified_in_snapshot":outcome.get("match_count")==1 and outcome.get("identity_matches") is True}))
            accepted=[c for c in validated if locator_accepted(c,meta,stability_threshold=self.stability_threshold)]
            primary=accepted[0] if accepted else validated[0]
            meta.update({"validation_url":self.page.url,"state_name":self.state_name})
            result.append(bundle.model_copy(update={"primary":primary.model_copy(update={"fallback":False}),
                "alternates":[c for c in validated if c is not primary],"metadata":meta}))
        return result

    def scan(self, application_url=None, *, page="global", validate=True, output_dir=None, element_names=None, identity_policies=None):
        from phoenix_smartlocatorai.dom_scanner import extract_interactable_elements, generate_locators_from_elements, _guess_custom_name
        from phoenix.locators.smartlocator_adaptor import convert_locators
        from phoenix.locators.reconciliation import bundle_matches_element
        # DOMContentLoaded only establishes the shell on client-rendered pages.
        # Capture, validation and scoped fallback must share the settled Page.
        self.wait_for_ready()
        html = self.page.content()
        elements=extract_interactable_elements(html)
        captured_count = len(elements)
        for policy in identity_policies or []:
            self.apply_content_identity(elements, policy)
        if element_names:
            elements=[e for e in elements if any(bundle_matches_element(n,
                {"element_name":_guess_custom_name(e),"metadata":{"element_data":e}}) for n in element_names)]
        raw=generate_locators_from_elements(elements)
        bundles=convert_locators(raw,page=page)
        bundles=self.revalidate(bundles) if validate else bundles
        if validate:
            bundles=self.capture_form_control_identities(bundles)
        self.scan_diagnostics = {"final_url":self.page.url,"state_name":self.state_name,
            "readiness":"settled", "captured_element_count":captured_count,
            "selected_element_count":len(elements), "converted_bundle_count":len(bundles),
            "dom_sha256":hashlib.sha256(html.encode()).hexdigest()}
        if output_dir:
            from pathlib import Path
            target=Path(output_dir); target.mkdir(parents=True,exist_ok=True)
            (target/"locators.json").write_text(json.dumps({"locators":raw,"capture":self.scan_diagnostics}),encoding="utf-8")
        return bundles

    def capture_form_control_identities(self, bundles):
        """Enrich only freshly accepted form controls on the owned scan Page.

        Never upgrade historical evidence during runtime validation. Existing
        bundles need a fresh scan before validation text can be disregarded.
        """
        from phoenix_shared.locator_policy import locator_accepted
        result=[]
        for bundle in bundles:
            metadata=dict(bundle.metadata or {})
            expected=metadata.get('element_data') or {}
            context=expected.get('ancestor_context') or {}
            if context.get('container_tag')!='form' or expected.get('content_identity') or not locator_accepted(bundle.primary,metadata):
                result.append(bundle);continue
            try:
                actual=locator_on_page(self.page,bundle.primary).evaluate(_DESCRIBE,None)
                profile=actual.get('form_identity')
                if not valid_form_control_identity(profile):
                    result.append(bundle);continue
                enriched={**expected,'form_control_identity':profile}
                upgraded=bundle.model_copy(update={'metadata':{**metadata,'element_data':enriched}})
                # Check the strengthened evidence, including global identity
                # uniqueness, before persisting it as accepted.
                outcome=self.validate(bundle.primary,{'element_data':enriched})
                result.append(upgraded if outcome.get('match_count')==1 and outcome.get('identity_matches') is True else bundle)
            except Exception:
                result.append(bundle)
        return result

    def apply_content_identity(self, elements, policy):
        """Capture an explicit display-slot contract; never infer mutable text."""
        selectors = policy.get('mutable_text_selectors')
        if not isinstance(selectors, list) or not selectors or not all(isinstance(s,str) and s.strip() for s in selectors):
            raise ValueError('Identity policy requires explicit relative display selectors')
        target = self.page.locator(policy['selector'])
        if target.count() != 1:
            raise ValueError('Identity policy must address one physical target')
        original = target.evaluate(_DESCRIBE)
        matching = [e for e in elements if identity_matches(original,e)]
        if len(matching) != 1:
            raise ValueError('Identity policy must bind one captured physical target')
        expected = matching[0]
        if not expected.get('interaction_evidence') and expected.get('tag') not in ('button','a'):
            raise ValueError('Display policy requires evidenced interaction semantics')
        masked = target.evaluate(_DESCRIBE, {'mutable_text_selectors':selectors})
        context = dict(expected.get('ancestor_context') or {})
        section = context.get('section_context') or {}
        if not expected.get('class') or not (any(section.get(k) for k in ('section_id','section_class','section_heading','section_test_id'))
                or context.get('container_id') or context.get('container_test_id')):
            raise ValueError('Display policy requires target structure and explicit section identity')
        if context.get('container_text'):
            captured_text = str(context['container_text']).casefold()
            ancestors = [i for i,a in enumerate(original['ancestors'])
                if a['tag'] == context.get('container_tag')
                and a['id'] == (context.get('container_id') or '')
                and a['class'] == (context.get('container_class') or '')
                and (captured_text in a['text'].casefold() or
                    (context.get('container_text_truncated') is True and captured_text == (a['text'][:47]+'...').casefold()))]
            if len(ancestors) != 1:
                raise ValueError('Cannot establish exact captured container for display policy')
            context['container_text'] = masked['ancestors'][ancestors[0]]['text']
        if context.get('distinguishing_text') in masked['mutable_display_values']:
            context['distinguishing_text'] = '[mutable-display]'
        expected['content_identity'] = {'version':1,'mutable_text_selectors':selectors,
            'structure':masked['content_structure'],'text':masked['text'],'ancestor_context':context}
        # Container text must not make two structurally indistinguishable triggers
        # appear distinct simply because their permitted display values differ.
        structural = {**expected,'content_identity':{**expected['content_identity'],
            'ancestor_context':{**context,'container_text':'','distinguishing_text':''}}}
        matches = 0
        anchors = self.page.locator(expected['tag'])
        if anchors.count() > 500:
            raise ValueError('Display policy exceeds bounded identity search')
        for node in anchors.all():
            try: matches += bool(identity_matches(node.evaluate(_DESCRIBE,structural['content_identity']),structural))
            except Exception: continue
        if matches != 1:
            raise ValueError('Display policy does not uniquely establish physical identity')
        result = self.validate(Locator(element_name='IdentityPolicy',strategy=LocatorStrategy.CSS,value=policy['selector']), {'element_data':expected})
        if result['identity_matches'] is not True:
            raise ValueError('Display policy does not uniquely establish physical identity')

    def capture(self, payload, round_number=1):
        """Find anchors from identity evidence, not by choosing a failed match."""
        data=payload.get("element_data") or {}
        snapshots=[]
        if data:
            # Bounded candidates. A large unresolved search remains unresolved.
            tag=str(data.get("tag") or "")
            selector=tag if re.fullmatch(r"[a-z][a-z0-9-]*", tag) else "button,input,a,select,textarea,[role]"
            nodes=self.page.locator(selector)
            if nodes.count()>500:
                return {"capture_status":"insufficient_context","capture_reason":"too_many_anchor_candidates"}
            for node in nodes.all():
                try: actual=node.evaluate(_DESCRIBE, data.get('content_identity'))
                except Exception: continue
                if identity_matches(actual,data):
                    snapshots.append(actual)
                    if len(snapshots)>=5:
                        break
        if not data and payload.get("candidate_elements"):
            for candidate in payload["candidate_elements"][:5]:
                cm = candidate.get("metadata") or {}
                expected = cm.get("element_data") or next((r.get("element_data") for r in
                    cm.get("smartlocator_raw_records", []) if r.get("element_data")), {})
                if expected:
                    capture = self.capture({"element_data": expected}, round_number)
                    if capture.get("capture_status") == "captured":
                        snapshots.append({"element_name": candidate.get("element_name"),
                                          "context": capture.get("scoped_dom")})
        encoded=json.dumps(snapshots,ensure_ascii=False)
        return {"capture_status":"captured" if snapshots else "insufficient_context",
                "scoped_dom":encoded[:14000], "context_truncated":len(encoded)>14000,
                "anchor_count":len(snapshots),"captured_at":datetime.now(timezone.utc).isoformat(),
                "page_url":self.page.url,"state_name":self.state_name,
                "context_fingerprint":hashlib.sha256(encoded.encode()).hexdigest()}


@contextmanager
def live_session(application_url, *, page=None, storage_state=None, state_name="global",
                 actions=None, stability_threshold=0.8):
    if page is not None:
        yield LiveLocatorSession(page,state_name=state_name,stability_threshold=stability_threshold)
        return
    from playwright.sync_api import sync_playwright
    if storage_state:
        from pathlib import Path
        state_path = Path(storage_state).expanduser().resolve()
        if not state_path.is_file():
            raise ValueError("Storage-state file does not exist")
        storage_state = str(state_path)
    from phoenix_smartlocatorai.dynamic_states import _execute_state_action
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            context=browser.new_context(**({"storage_state":storage_state} if storage_state else {}))
            current=context.new_page()
            current.goto(application_url,wait_until="domcontentloaded")
            for action in actions or []:
                _execute_state_action(current,action)
            yield LiveLocatorSession(current,state_name=state_name,stability_threshold=stability_threshold)
        finally:
            active_error = sys.exc_info()[0] is not None
            try:
                browser.close()
            except Exception:
                # Preserve the operation's original failure. A disconnected
                # Playwright driver during cleanup must not hide the error
                # raised by locator reconciliation or generation.
                if not active_error:
                    raise
