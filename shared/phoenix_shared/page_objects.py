"""Evidence-driven page objects and ordered expansion for artifact verification."""
from __future__ import annotations
import ast
import hashlib
import re
from urllib.parse import urlsplit


def _slug(value):
    value=re.sub(r'([a-z0-9])([A-Z])',r'\1_\2',value)
    result=re.sub(r'[^a-z0-9]+','_',value.lower()).strip('_') or 'document'
    return 'page_'+result if result[0].isdigit() else result


def synthesize_pages(script, module_name, test_name, fixture='page'):
    tree=ast.parse(script)
    fn=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')),None)
    if fn is None:return None
    groups={};ordered=[];owner='document';chunk=[];provenance={};route_owners={}
    for node in ast.walk(fn):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'validate_target','assert_contract'} and len(node.args)>1:
            try:
                data=ast.literal_eval(node.args[1]);data=data if node.func.id=='validate_target' else data.get('target_evidence',{})
                meta=(data.get('primary') or {}).get('metadata') or {}
                if meta.get('validation_url'):route_owners.setdefault(meta['validation_url'],_slug(data.get('page') or meta.get('state_name') or urlsplit(meta['validation_url']).path))
            except (ValueError,TypeError):pass
    dependencies=ast.unparse(ast.Module(body=[n for n in tree.body if n is not fn and not (isinstance(n,ast.ImportFrom) and n.module=='__future__') and not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))],type_ignores=[]))
    def flush():
        nonlocal chunk
        if not chunk:return
        code=ast.unparse(ast.Module(body=chunk,type_ignores=[]))
        method='perform_'+hashlib.sha256(code.encode()).hexdigest()[:12]
        groups.setdefault(owner,{})[method]=code;ordered.append((owner,method));chunk=[]
    for statement in fn.body:
        evidence=[];navigation=None;destination_fragment=None
        for node in ast.walk(statement):
            if not isinstance(node,ast.Call):continue
            if isinstance(node.func,ast.Attribute) and node.func.attr=='to_have_url' and node.args:
                value=node.args[0]
                if isinstance(value,ast.Call) and value.args:value=value.args[0]
                if isinstance(value,ast.Constant) and isinstance(value.value,str) and value.value.startswith('/') and not re.search(r'[\\^$.*+?{}\[\]|()]',value.value):destination_fragment=value.value
            if isinstance(node.func,ast.Attribute) and node.func.attr=='goto' and node.args and isinstance(node.args[0],ast.Constant):navigation=node.args[0].value
            if isinstance(node.func,ast.Name) and node.func.id in {'validate_target','assert_contract'} and len(node.args)>1:
                try:
                    data=ast.literal_eval(node.args[1])
                    if node.func.id=='assert_contract':data=data.get('target_evidence') or {}
                    if data.get('primary'):evidence.append(data)
                except (ValueError,TypeError):pass
        proposed=owner
        if navigation:proposed=route_owners.get(navigation,_slug(urlsplit(navigation).path))
        if destination_fragment:
            known={name for route,name in route_owners.items() if destination_fragment in route}
            proposed=next(iter(known)) if len(known)==1 else _slug(destination_fragment)
        if evidence:
            data=evidence[0];meta=data['primary'].get('metadata') or {}
            url=meta.get('validation_url')
            # UI state owns controls from post-interaction captures.
            proposed=_slug(data.get('page') or meta.get('state_name') or (urlsplit(url).path if url else owner))
            for item in evidence:
                key=item['element_name']
                provenance.setdefault(proposed,{})[key]=item
        if proposed!=owner:
            if owner!='document' or groups:flush()
            owner=proposed
        chunk.append(statement)
    flush()
    if not groups:return None
    locals_={n.id for n in ast.walk(fn) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
    class Rebind(ast.NodeTransformer):
        def visit_Name(self,node):
            if node.id=='page':return ast.Attribute(value=ast.Name(id='self',ctx=ast.Load()),attr='_page',ctx=node.ctx)
            if node.id in locals_:return ast.Subscript(value=ast.Name(id='context',ctx=ast.Load()),slice=ast.Constant(node.id),ctx=node.ctx)
            return node
    objects=[];imports=[];initializers=[]
    class Accessors(ast.NodeTransformer):
        def __init__(self, expressions):self.expressions=expressions
        def visit_Call(self,node):
            key=ast.unparse(node)
            if key in self.expressions:return ast.Call(func=ast.Attribute(value=ast.Name(id='self',ctx=ast.Load()),attr=self.expressions[key],ctx=ast.Load()),args=[],keywords=[])
            return self.generic_visit(node)
    for name,methods in groups.items():
        class_name=''.join(w.capitalize() for w in name.split('_'))+'Page'
        # A stable page/dependency identity lets the output coordinator extend
        # methods across tests without overwriting unrelated workflows.
        domains=sorted({urlsplit(url).scheme+'://'+urlsplit(url).netloc for url in route_owners})
        identity=hashlib.sha256(repr((dependencies,domains,name)).encode()).hexdigest()[:10]
        filename=f'{name}_{identity}_page'
        imports.append(f'from pages.{filename} import {class_name}')
        initializers.append(f'    _po_{name} = {class_name}({fixture})')
        code='from __future__ import annotations\n'+dependencies+'\nfrom pages.base_page import BasePage\n\n'
        code+=f'class {class_name}(BasePage):\n'
        from phoenix_shared.models.locator import Locator
        accessors={};accessor_evidence={}
        for element,evidence in provenance.get(name,{}).items():
            expression=Locator.model_validate({**evidence['primary'],'element_name':element}).to_playwright()
            accessor='locate_'+_slug(element)+'_'+hashlib.sha256(expression.encode()).hexdigest()[:8]
            accessor_evidence[accessor]=evidence
            accessors[ast.unparse(ast.parse(expression,mode='eval').body)]=accessor
            adapted=Rebind().visit(ast.parse(expression,mode='eval'));ast.fix_missing_locations(adapted)
            code+=f'\n    def {accessor}(self):\n        return '+ast.unparse(adapted)+'\n'
        code+='\n    LOCATOR_PROVENANCE = '+repr(accessor_evidence)+'\n'
        for method,body in methods.items():
            adapted=Accessors(accessors).visit(ast.parse(body))
            adapted=Rebind().visit(adapted);ast.fix_missing_locations(adapted)
            code+=f'\n    def {method}(self, context):\n'+ '\n'.join('        '+line for line in ast.unparse(adapted).splitlines())+'\n'
        objects.append({'action':'extend','file':f'pages/{filename}.py','class_name':class_name,'code':code,'page':name,'locator_provenance':provenance.get(name,{})})
    test_code='from __future__ import annotations\nfrom playwright.sync_api import Page\n'+'\n'.join(imports)+f'\n\ndef test_{test_name}({fixture}: Page):\n    context = {{}}\n'+'\n'.join(initializers)+'\n'
    test_code+=''.join(f'    _po_{name}.{method}(context)\n' for name,method in ordered)
    return {'page_objects':objects,'tests':[{'action':'extend','file':f'tests/{module_name}/test_{test_name}.py','code':test_code}],
            'locators':[],'test_data':[],'architecture':'page_state','execution_order':ordered}


def expanded_pom_script(bundle):
    """Inspect actual imports, instances, and calls; do not trust plan metadata."""
    classes={}
    for artifact in bundle.get('page_objects',[]):
        tree=ast.parse(artifact['code'])
        for cls in (n for n in tree.body if isinstance(n,ast.ClassDef)):
            classes[(artifact['file'].replace('/','.').removesuffix('.py'),cls.name)]={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    body=[]
    class Restore(ast.NodeTransformer):
        def __init__(self, methods):self.methods=methods
        def visit_Call(self,node):
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='self' and node.func.attr.startswith('locate_'):
                getter=self.methods.get(node.func.attr)
                if getter is None or len(getter.body)!=1 or not isinstance(getter.body[0],ast.Return):raise ValueError('Invalid locator accessor')
                return ast.parse(ast.unparse(getter.body[0].value),mode='eval').body
            return self.generic_visit(node)
        def visit_Subscript(self,node):
            if isinstance(node.value,ast.Name) and node.value.id=='context' and isinstance(node.slice,ast.Constant):return ast.Name(id=node.slice.value,ctx=node.ctx)
            return self.generic_visit(node)
    for artifact in bundle.get('tests',[]):
        tree=ast.parse(artifact['code']);imports={};instances={}
        for n in tree.body:
            if isinstance(n,ast.ImportFrom):
                for alias in n.names:imports[alias.asname or alias.name]=(n.module,alias.name)
        fn=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')),None)
        if not fn:raise ValueError('Missing generated POM test')
        for statement in fn.body:
            if isinstance(statement,ast.Assign) and isinstance(statement.value,ast.Call) and isinstance(statement.value.func,ast.Name):
                key=imports.get(statement.value.func.id)
                if key in classes:instances[statement.targets[0].id]=classes[key];continue
            if isinstance(statement,ast.Expr) and isinstance(statement.value,ast.Call):
                call=statement.value
                if isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id in instances:
                    method=instances[call.func.value.id].get(call.func.attr)
                    if method is None:raise ValueError('Unresolved POM method call')
                    # Copy through AST text so inspection never mutates artifacts.
                    body.extend(Restore(instances[call.func.value.id]).visit(ast.parse(ast.unparse(n))).body[0] for n in method.body);continue
                raise ValueError('Unaccounted test operation outside page objects')
    module=ast.Module(body=[ast.FunctionDef(name='test_expanded',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=body or [ast.Pass()],decorator_list=[])],type_ignores=[])
    ast.fix_missing_locations(module)
    return ast.unparse(module)
