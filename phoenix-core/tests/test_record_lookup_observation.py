from types import SimpleNamespace
import pytest
from phoenix.locators.record_lookup_observation import observe_record_lookup


def response(url='https://fixture/api/items?offset=0&limit=2',method='GET',data=None):
    return SimpleNamespace(url=url,request=SimpleNamespace(method=method),json=lambda:data or {
        'data':[{'recordId':1,'firstName':'private name','lastName':'private surname'},{'recordId':2,'firstName':'other','lastName':'other'}],
        'meta':{'total':5}})


def test_observation_stores_only_schema_and_lookup_not_record_values():
    result=observe_record_lookup(response(),'https://fixture/login')
    assert len(result)==1 and result[0]['lookup']['identity_paths']==[['recordId']]
    assert 'private name' not in str(result) and 'private surname' not in str(result)
    assert result[0]['lookup']['records_path']==['data']
    assert result[0]['lookup']['total_path']==['meta','total']


@pytest.mark.parametrize('r',[response(method='POST'),response(url='https://other/api?offset=0&limit=2'),response(url='https://fixture/api?offset=0&limit=2&token=secret'),response(url='https://fixture/api')])
def test_non_read_only_external_sensitive_or_unpaginated_sources_not_inferred(r):
    assert observe_record_lookup(r,'https://fixture/login')==[]
