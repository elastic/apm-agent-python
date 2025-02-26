---
mapped_pages:
  - https://www.elastic.co/guide/en/apm/agent/python/current/supported-technologies.html
---

# Supported technologies [supported-technologies]

$$$framework-support$$$
The Elastic APM Python Agent comes with support for the following frameworks:

* [Django](/reference/django-support.md)
* [Flask](/reference/flask-support.md)
* [Aiohttp Server](#supported-aiohttp)
* [Tornado](#supported-tornado)
* [Starlette/FastAPI](#supported-starlette)
* [Sanic](#supported-sanic)
* [GRPC](#supported-grpc)

For other frameworks and custom Python code, the agent exposes a set of [APIs](/reference/api-reference.md) for integration.


### Python [supported-python]

The following Python versions are supported:

* 3.6
* 3.7
* 3.8
* 3.9
* 3.10
* 3.11
* 3.12


### Django [supported-django]

We support these Django versions:

* 1.11
* 2.0
* 2.1
* 2.2
* 3.0
* 3.1
* 3.2
* 4.0
* 4.2
* 5.0

For upcoming Django versions, we generally aim to ensure compatibility starting with the first Release Candidate.

::::{note}
we currently don’t support Django running in ASGI mode.
::::



### Flask [supported-flask]

We support these Flask versions:

* 0.10 (Deprecated)
* 0.11 (Deprecated)
* 0.12 (Deprecated)
* 1.0
* 1.1
* 2.0
* 2.1
* 2.2
* 2.3
* 3.0


### Aiohttp Server [supported-aiohttp]

We support these aiohttp versions:

* 3.0+


### Tornado [supported-tornado]

We support these tornado versions:

* 6.0+


### Sanic [supported-sanic]

We support these sanic versions:

* 20.12.2+


### Starlette/FastAPI [supported-starlette]

We support these Starlette versions:

* 0.13.0+

Any FastAPI version which uses a supported Starlette version should also be supported.


### GRPC [supported-grpc]

We support these `grpcio` versions:

* 1.24.0+


## Automatic Instrumentation [automatic-instrumentation]

The Python APM agent comes with automatic instrumentation of various 3rd party modules and standard library modules.


### Scheduling [automatic-instrumentation-scheduling]


##### Celery [automatic-instrumentation-scheduling-celery]

We support these Celery versions:

* 4.x (deprecated)
* 5.x

Celery tasks will be recorded automatically with Django and Flask only.


### Databases [automatic-instrumentation-db]


#### Elasticsearch [automatic-instrumentation-db-elasticsearch]

Instrumented methods:

* `elasticsearch.transport.Transport.perform_request`
* `elasticsearch.connection.http_urllib3.Urllib3HttpConnection.perform_request`
* `elasticsearch.connection.http_requests.RequestsHttpConnection.perform_request`
* `elasticsearch._async.transport.AsyncTransport.perform_request`
* `elasticsearch_async.connection.AIOHttpConnection.perform_request`

Additionally, the instrumentation wraps the following methods of the `Elasticsearch` client class:

* `elasticsearch.client.Elasticsearch.delete_by_query`
* `elasticsearch.client.Elasticsearch.search`
* `elasticsearch.client.Elasticsearch.count`
* `elasticsearch.client.Elasticsearch.update`

Collected trace data:

* the query string (if available)
* the `query` element from the request body (if available)
* the response status code
* the count of affected rows (if available)

We recommend using keyword arguments only with elasticsearch-py, as recommended by [the elasticsearch-py docs](https://elasticsearch-py.readthedocs.io/en/master/api.html#api-documentation). If you are using positional arguments, we will be unable to gather the `query` element from the request body.


#### SQLite [automatic-instrumentation-db-sqlite]

Instrumented methods:

* `sqlite3.connect`
* `sqlite3.dbapi2.connect`
* `pysqlite2.dbapi2.connect`

The instrumented `connect` method returns a wrapped connection/cursor which instruments the actual `Cursor.execute` calls.

Collected trace data:

* parametrized SQL query


#### MySQLdb [automatic-instrumentation-db-mysql]

Library: `MySQLdb`

Instrumented methods:

* `MySQLdb.connect`

The instrumented `connect` method returns a wrapped connection/cursor which instruments the actual `Cursor.execute` calls.

Collected trace data:

* parametrized SQL query


#### mysql-connector [automatic-instrumentation-db-mysql-connector]

Library: `mysql-connector-python`

Instrumented methods:

* `mysql.connector.connect`

The instrumented `connect` method returns a wrapped connection/cursor which instruments the actual `Cursor.execute` calls.

Collected trace data:

* parametrized SQL query


#### pymysql [automatic-instrumentation-db-pymysql]

Library: `pymysql`

Instrumented methods:

* `pymysql.connect`

The instrumented `connect` method returns a wrapped connection/cursor which instruments the actual `Cursor.execute` calls.

Collected trace data:

* parametrized SQL query


#### aiomysql [automatic-instrumentation-db-aiomysql]

Library: `aiomysql`

Instrumented methods:

* `aiomysql.cursors.Cursor.execute`

Collected trace data:

* parametrized SQL query


#### PostgreSQL [automatic-instrumentation-db-postgres]

Library: `psycopg2`, `psycopg2-binary` (`>=2.9`)

Instrumented methods:

* `psycopg2.connect`

The instrumented `connect` method returns a wrapped connection/cursor which instruments the actual `Cursor.execute` calls.

Collected trace data:

* parametrized SQL query


#### aiopg [automatic-instrumentation-db-aiopg]

Library: `aiopg` (`>=1.0`)

Instrumented methods:

* `aiopg.cursor.Cursor.execute`
* `aiopg.cursor.Cursor.callproc`

Collected trace data:

* parametrized SQL query


#### asyncpg [automatic-instrumentation-db-asyncg]

Library: `asyncpg` (`>=0.20`)

Instrumented methods:

* `asyncpg.connection.Connection.execute`
* `asyncpg.connection.Connection.executemany`

Collected trace data:

* parametrized SQL query


#### PyODBC [automatic-instrumentation-db-pyodbc]

Library: `pyodbc`, (`>=4.0`)

Instrumented methods:

* `pyodbc.connect`

The instrumented `connect` method returns a wrapped connection/cursor which instruments the actual `Cursor.execute` calls.

Collected trace data:

* parametrized SQL query


#### MS-SQL [automatic-instrumentation-db-mssql]

Library: `pymssql`, (`>=2.1.0`)

Instrumented methods:

* `pymssql.connect`

The instrumented `connect` method returns a wrapped connection/cursor which instruments the actual `Cursor.execute` calls.

Collected trace data:

* parametrized SQL query


#### MongoDB [automatic-instrumentation-db-mongodb]

Library: `pymongo`, `>=2.9,<3.8`

Instrumented methods:

* `pymongo.collection.Collection.aggregate`
* `pymongo.collection.Collection.bulk_write`
* `pymongo.collection.Collection.count`
* `pymongo.collection.Collection.create_index`
* `pymongo.collection.Collection.create_indexes`
* `pymongo.collection.Collection.delete_many`
* `pymongo.collection.Collection.delete_one`
* `pymongo.collection.Collection.distinct`
* `pymongo.collection.Collection.drop`
* `pymongo.collection.Collection.drop_index`
* `pymongo.collection.Collection.drop_indexes`
* `pymongo.collection.Collection.ensure_index`
* `pymongo.collection.Collection.find_and_modify`
* `pymongo.collection.Collection.find_one`
* `pymongo.collection.Collection.find_one_and_delete`
* `pymongo.collection.Collection.find_one_and_replace`
* `pymongo.collection.Collection.find_one_and_update`
* `pymongo.collection.Collection.group`
* `pymongo.collection.Collection.inline_map_reduce`
* `pymongo.collection.Collection.insert`
* `pymongo.collection.Collection.insert_many`
* `pymongo.collection.Collection.insert_one`
* `pymongo.collection.Collection.map_reduce`
* `pymongo.collection.Collection.reindex`
* `pymongo.collection.Collection.remove`
* `pymongo.collection.Collection.rename`
* `pymongo.collection.Collection.replace_one`
* `pymongo.collection.Collection.save`
* `pymongo.collection.Collection.update`
* `pymongo.collection.Collection.update_many`
* `pymongo.collection.Collection.update_one`

Collected trace data:

* database name
* method name


#### Redis [automatic-instrumentation-db-redis]

Library: `redis` (`>=2.8`)

Instrumented methods:

* `redis.client.Redis.execute_command`
* `redis.client.Pipeline.execute`

Collected trace data:

* Redis command name


#### aioredis [automatic-instrumentation-db-aioredis]

Library: `aioredis` (`<2.0`)

Instrumented methods:

* `aioredis.pool.ConnectionsPool.execute`
* `aioredis.commands.transaction.Pipeline.execute`
* `aioredis.connection.RedisConnection.execute`

Collected trace data:

* Redis command name


#### Cassandra [automatic-instrumentation-db-cassandra]

Library: `cassandra-driver` (`>=3.4,<4.0`)

Instrumented methods:

* `cassandra.cluster.Session.execute`
* `cassandra.cluster.Cluster.connect`

Collected trace data:

* CQL query


#### Python Memcache [automatic-instrumentation-db-python-memcache]

Library: `python-memcached` (`>=1.51`)

Instrumented methods:

* `memcache.Client.add`
* `memcache.Client.append`
* `memcache.Client.cas`
* `memcache.Client.decr`
* `memcache.Client.delete`
* `memcache.Client.delete_multi`
* `memcache.Client.disconnect_all`
* `memcache.Client.flush_all`
* `memcache.Client.get`
* `memcache.Client.get_multi`
* `memcache.Client.get_slabs`
* `memcache.Client.get_stats`
* `memcache.Client.gets`
* `memcache.Client.incr`
* `memcache.Client.prepend`
* `memcache.Client.replace`
* `memcache.Client.set`
* `memcache.Client.set_multi`
* `memcache.Client.touch`

Collected trace data:

* Destination (address and port)


#### pymemcache [automatic-instrumentation-db-pymemcache]

Library: `pymemcache` (`>=3.0`)

Instrumented methods:

* `pymemcache.client.base.Client.add`
* `pymemcache.client.base.Client.append`
* `pymemcache.client.base.Client.cas`
* `pymemcache.client.base.Client.decr`
* `pymemcache.client.base.Client.delete`
* `pymemcache.client.base.Client.delete_many`
* `pymemcache.client.base.Client.delete_multi`
* `pymemcache.client.base.Client.flush_all`
* `pymemcache.client.base.Client.get`
* `pymemcache.client.base.Client.get_many`
* `pymemcache.client.base.Client.get_multi`
* `pymemcache.client.base.Client.gets`
* `pymemcache.client.base.Client.gets_many`
* `pymemcache.client.base.Client.incr`
* `pymemcache.client.base.Client.prepend`
* `pymemcache.client.base.Client.quit`
* `pymemcache.client.base.Client.replace`
* `pymemcache.client.base.Client.set`
* `pymemcache.client.base.Client.set_many`
* `pymemcache.client.base.Client.set_multi`
* `pymemcache.client.base.Client.stats`
* `pymemcache.client.base.Client.touch`

Collected trace data:

* Destination (address and port)


#### kafka-python [automatic-instrumentation-db-kafka-python]

Library: `kafka-python` (`>=2.0`)

Instrumented methods:

* `kafka.KafkaProducer.send`,
* `kafka.KafkaConsumer.poll`,
* `kafka.KafkaConsumer.\\__next__`

Collected trace data:

* Destination (address and port)
* topic (if applicable)


### External HTTP requests [automatic-instrumentation-http]


#### Standard library [automatic-instrumentation-stdlib-urllib]

Library: `urllib2` (Python 2) / `urllib.request` (Python 3)

Instrumented methods:

* `urllib2.AbstractHTTPHandler.do_open` / `urllib.request.AbstractHTTPHandler.do_open`

Collected trace data:

* HTTP method
* requested URL


#### urllib3 [automatic-instrumentation-urllib3]

Library: `urllib3`

Instrumented methods:

* `urllib3.connectionpool.HTTPConnectionPool.urlopen`

Additionally, we instrumented vendored instances of urllib3 in the following libraries:

* `requests`
* `botocore`

Both libraries have "unvendored" urllib3 in more recent versions, we recommend to use the newest versions.

Collected trace data:

* HTTP method
* requested URL


#### requests [automatic-instrumentation-requests]

Instrumented methods:

* `requests.sessions.Session.send`

Collected trace data:

* HTTP method
* requested URL


#### AIOHTTP Client [automatic-instrumentation-aiohttp-client]

Instrumented methods:

* `aiohttp.client.ClientSession._request`

Collected trace data:

* HTTP method
* requested URL


#### httpx [automatic-instrumentation-httpx]

Instrumented methods:

* `httpx.Client.send

Collected trace data:

* HTTP method
* requested URL


### Services [automatic-instrumentation-services]


#### AWS Boto3 / Botocore [automatic-instrumentation-boto3]

Library: `boto3` (`>=1.0`)

Instrumented methods:

* `botocore.client.BaseClient._make_api_call`

Collected trace data for all services:

* AWS region (e.g. `eu-central-1`)
* AWS service name (e.g. `s3`)
* operation name (e.g. `ListBuckets`)

Additionally, some services collect more specific data


#### AWS Aiobotocore [automatic-instrumentation-aiobotocore]

Library: `aiobotocore` (`>=2.2.0`)

Instrumented methods:

* `aiobotocore.client.BaseClient._make_api_call`

Collected trace data for all services:

* AWS region (e.g. `eu-central-1`)
* AWS service name (e.g. `s3`)
* operation name (e.g. `ListBuckets`)

Additionally, some services collect more specific data


##### S3 [automatic-instrumentation-s3]

* Bucket name


##### DynamoDB [automatic-instrumentation-dynamodb]

* Table name


##### SNS [automatic-instrumentation-sns]

* Topic name


##### SQS [automatic-instrumentation-sqs]

* Queue name


### Template Engines [automatic-instrumentation-template-engines]


#### Django Template Language [automatic-instrumentation-dtl]

Library: `Django` (see [Django](#supported-django) for supported versions)

Instrumented methods:

* `django.template.Template.render`

Collected trace data:

* template name


#### Jinja2 [automatic-instrumentation-jinja2]

Library: `jinja2`

Instrumented methods:

* `jinja2.Template.render`

Collected trace data:

* template name

