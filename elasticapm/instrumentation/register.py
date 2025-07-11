#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from elasticapm.utils.module_import import import_string

_cls_register = {
    "elasticapm.instrumentation.packages.botocore.BotocoreInstrumentation",
    "elasticapm.instrumentation.packages.httpx.sync.httpx.HttpxClientInstrumentation",
    "elasticapm.instrumentation.packages.jinja2.Jinja2Instrumentation",
    "elasticapm.instrumentation.packages.psycopg.PsycopgInstrumentation",
    "elasticapm.instrumentation.packages.psycopg2.Psycopg2Instrumentation",
    "elasticapm.instrumentation.packages.psycopg2.Psycopg2ExtensionsInstrumentation",
    "elasticapm.instrumentation.packages.mysql.MySQLInstrumentation",
    "elasticapm.instrumentation.packages.mysql_connector.MySQLConnectorInstrumentation",
    "elasticapm.instrumentation.packages.pymysql.PyMySQLConnectorInstrumentation",
    "elasticapm.instrumentation.packages.pylibmc.PyLibMcInstrumentation",
    "elasticapm.instrumentation.packages.pymongo.PyMongoInstrumentation",
    "elasticapm.instrumentation.packages.pymongo.PyMongoBulkInstrumentation",
    "elasticapm.instrumentation.packages.pymongo.PyMongoCursorInstrumentation",
    "elasticapm.instrumentation.packages.python_memcached.PythonMemcachedInstrumentation",
    "elasticapm.instrumentation.packages.pymemcache.PyMemcacheInstrumentation",
    "elasticapm.instrumentation.packages.redis.RedisInstrumentation",
    "elasticapm.instrumentation.packages.redis.RedisPipelineInstrumentation",
    "elasticapm.instrumentation.packages.redis.RedisConnectionInstrumentation",
    "elasticapm.instrumentation.packages.requests.RequestsInstrumentation",
    "elasticapm.instrumentation.packages.sqlite.SQLiteInstrumentation",
    "elasticapm.instrumentation.packages.urllib3.Urllib3Instrumentation",
    "elasticapm.instrumentation.packages.elasticsearch.ElasticsearchConnectionInstrumentation",
    "elasticapm.instrumentation.packages.elasticsearch.ElasticsearchTransportInstrumentation",
    "elasticapm.instrumentation.packages.cassandra.CassandraInstrumentation",
    "elasticapm.instrumentation.packages.pymssql.PyMSSQLInstrumentation",
    "elasticapm.instrumentation.packages.pyodbc.PyODBCInstrumentation",
    "elasticapm.instrumentation.packages.django.template.DjangoTemplateInstrumentation",
    "elasticapm.instrumentation.packages.django.template.DjangoTemplateSourceInstrumentation",
    "elasticapm.instrumentation.packages.urllib.UrllibInstrumentation",
    "elasticapm.instrumentation.packages.graphql.GraphQLExecutorInstrumentation",
    "elasticapm.instrumentation.packages.graphql.GraphQLBackendInstrumentation",
    "elasticapm.instrumentation.packages.httpx.sync.httpcore.HTTPCoreInstrumentation",
    "elasticapm.instrumentation.packages.httplib2.Httplib2Instrumentation",
    "elasticapm.instrumentation.packages.azure.AzureInstrumentation",
    "elasticapm.instrumentation.packages.kafka.KafkaInstrumentation",
    "elasticapm.instrumentation.packages.grpc.GRPCClientInstrumentation",
    "elasticapm.instrumentation.packages.grpc.GRPCServerInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.sleep.AsyncIOSleepInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.aiohttp_client.AioHttpClientInstrumentation",
    "elasticapm.instrumentation.packages.httpx.async.httpx.HttpxAsyncClientInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.elasticsearch.ElasticSearchAsyncConnection",
    "elasticapm.instrumentation.packages.asyncio.elasticsearch.ElasticsearchAsyncTransportInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.aiopg.AioPGInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.asyncpg.AsyncPGInstrumentation",
    "elasticapm.instrumentation.packages.tornado.TornadoRequestExecuteInstrumentation",
    "elasticapm.instrumentation.packages.tornado.TornadoHandleRequestExceptionInstrumentation",
    "elasticapm.instrumentation.packages.tornado.TornadoRenderInstrumentation",
    "elasticapm.instrumentation.packages.httpx.async.httpcore.HTTPCoreAsyncInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.aioredis.RedisConnectionPoolInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.aioredis.RedisPipelineInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.aioredis.RedisConnectionInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.aiomysql.AioMySQLInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.aiobotocore.AioBotocoreInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.starlette.StarletteServerErrorMiddlewareInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.redis_asyncio.RedisAsyncioInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.redis_asyncio.RedisPipelineInstrumentation",
    "elasticapm.instrumentation.packages.asyncio.psycopg_async.AsyncPsycopgInstrumentation",
    "elasticapm.instrumentation.packages.grpc.GRPCAsyncServerInstrumentation",
}

# These instrumentations should only be enabled if we're instrumenting via the
# wrapper script, which calls register_wrapper_instrumentations() below.
_wrapper_register = {
    "elasticapm.instrumentation.packages.flask.FlaskInstrumentation",
    "elasticapm.instrumentation.packages.django.DjangoAutoInstrumentation",
    "elasticapm.instrumentation.packages.starlette.StarletteInstrumentation",
}


def register(cls) -> None:
    _cls_register.add(cls)


def register_wrapper_instrumentations() -> None:
    _cls_register.update(_wrapper_register)


_instrumentation_singletons = {}


def get_instrumentation_objects():
    for cls_str in _cls_register:
        if cls_str not in _instrumentation_singletons:
            cls = import_string(cls_str)
            _instrumentation_singletons[cls_str] = cls()

        obj = _instrumentation_singletons[cls_str]
        yield obj
