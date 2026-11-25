from django.urls import reverse
from drf_spectacular.generators import SchemaGenerator


def test_schema_excludes_version_prefix():
    schema = SchemaGenerator().get_schema(public=True)

    assert reverse('redoc') == '/v2/'
    assert reverse('metrics:metrics-list') == '/v2/metrics/'
    assert schema['servers'][0]['url'].rstrip('/').endswith('/v2')
    assert all(not path.startswith('/v2/') for path in schema['paths'])

    operation = schema['paths']['/metrics/']['get']
    assert operation['tags'] == ['metrics']
    assert operation['operationId'] == 'metrics_list'

    for path in schema['paths'].values():
        for operation in path.values():
            assert 'v2' not in operation.get('tags', [])
            assert not operation['operationId'].startswith('v2_')
