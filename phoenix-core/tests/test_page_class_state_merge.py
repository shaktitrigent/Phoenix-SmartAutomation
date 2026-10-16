"""Persist independently generated page classes without detaching their methods."""
import ast
from phoenix.output.coordinator import OutputManager


def test_two_scenario_classes_share_module_and_keep_their_assertions(tmp_path):
    manager=OutputManager(tmp_path)
    first='class EntryPage:\n    def access(self, page):\n        assert page == "entry"\n'
    second='import re\nclass RejectionPage:\n    def reject(self, page):\n        assert re.fullmatch("rejected",page)\n'
    for name,code in [('EntryPage',first),('RejectionPage',second)]:
        manager.apply({'page_objects':[{'action':'extend','file':'pages/access.py','class_name':name,'code':code}]})
    stored=(tmp_path/'pages/access.py').read_text()
    namespace={};exec(stored,namespace)
    namespace['EntryPage']().access('entry')
    namespace['RejectionPage']().reject('rejected')
    assert not hasattr(namespace['EntryPage'],'reject')
    assert {n.name for n in ast.parse(stored).body if isinstance(n,ast.ClassDef)}=={'EntryPage','RejectionPage'}
    manager.apply({'page_objects':[{'action':'extend','file':'pages/access.py','class_name':'RejectionPage','code':second.replace('"rejected"','"denied"')}]})
    namespace={};exec((tmp_path/'pages/access.py').read_text(),namespace)
    namespace['EntryPage']().access('entry')
    namespace['RejectionPage']().reject('denied')
