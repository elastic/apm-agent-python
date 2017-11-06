import os
import random
import shutil
import sys
import tempfile

import pytest

from elasticapm.contrib.zerorpc import Middleware

zerorpc = pytest.importorskip("zerorpc")
gevent = pytest.importorskip("gevent")



has_unsupported_pypy = (hasattr(sys, 'pypy_version_info')
                        and sys.pypy_version_info < (2, 6))



@pytest.mark.skipif(has_unsupported_pypy, reason='Failure with pypy < 2.6')
def test_zerorpc_middleware_with_reqrep(elasticapm_client):
    tmpdir = tempfile.mkdtemp()
    server_endpoint = 'ipc://{0}'.format(os.path.join(tmpdir, 'random_zeroserver'))
    try:
        zerorpc.Context.get_instance().register_middleware(Middleware(
            client=elasticapm_client
        ))
        server = zerorpc.Server(random)
        server.bind(server_endpoint)
        gevent.spawn(server.run)

        client = zerorpc.Client()
        client.connect(server_endpoint)

        with pytest.raises(zerorpc.exceptions.RemoteError) as excinfo:
            client.choice([])

        client.close()
        server.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    ex = excinfo.value
    assert ex.name == 'IndexError'
    assert len(elasticapm_client.events) == 1
    exc = elasticapm_client.events[0]['errors'][0]['exception']
    assert exc['type'] == 'IndexError'
    frames = exc['stacktrace']
    assert frames[0]['function'] == 'choice'
    assert frames[0]['module'] == 'random'
