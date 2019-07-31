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

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class PyMongoInstrumentation(AbstractInstrumentedModule):
    name = "pymongo"

    instrument_list = [
        ("pymongo.collection", "Collection.aggregate"),
        ("pymongo.collection", "Collection.bulk_write"),
        ("pymongo.collection", "Collection.count"),
        ("pymongo.collection", "Collection.create_index"),
        ("pymongo.collection", "Collection.create_indexes"),
        ("pymongo.collection", "Collection.delete_many"),
        ("pymongo.collection", "Collection.delete_one"),
        ("pymongo.collection", "Collection.distinct"),
        ("pymongo.collection", "Collection.drop"),
        ("pymongo.collection", "Collection.drop_index"),
        ("pymongo.collection", "Collection.drop_indexes"),
        ("pymongo.collection", "Collection.ensure_index"),
        ("pymongo.collection", "Collection.find_and_modify"),
        ("pymongo.collection", "Collection.find_one"),
        ("pymongo.collection", "Collection.find_one_and_delete"),
        ("pymongo.collection", "Collection.find_one_and_replace"),
        ("pymongo.collection", "Collection.find_one_and_update"),
        ("pymongo.collection", "Collection.group"),
        ("pymongo.collection", "Collection.inline_map_reduce"),
        ("pymongo.collection", "Collection.insert"),
        ("pymongo.collection", "Collection.insert_many"),
        ("pymongo.collection", "Collection.insert_one"),
        ("pymongo.collection", "Collection.map_reduce"),
        ("pymongo.collection", "Collection.reindex"),
        ("pymongo.collection", "Collection.remove"),
        ("pymongo.collection", "Collection.rename"),
        ("pymongo.collection", "Collection.replace_one"),
        ("pymongo.collection", "Collection.save"),
        ("pymongo.collection", "Collection.update"),
        ("pymongo.collection", "Collection.update_many"),
        ("pymongo.collection", "Collection.update_one"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        cls_name, method_name = method.split(".", 1)
        signature = ".".join([instance.full_name, method_name])
        with capture_span(signature, span_type="db", span_subtype="mongodb", span_action="query", leaf=True):
            return wrapped(*args, **kwargs)


class PyMongoBulkInstrumentation(AbstractInstrumentedModule):
    name = "pymongo"

    instrument_list = [("pymongo.bulk", "BulkOperationBuilder.execute")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        collection = instance._BulkOperationBuilder__bulk.collection
        signature = ".".join([collection.full_name, "bulk.execute"])
        with capture_span(signature, span_type="db", span_subtype="mongodb", span_action="query"):
            return wrapped(*args, **kwargs)


class PyMongoCursorInstrumentation(AbstractInstrumentedModule):
    name = "pymongo"

    instrument_list = [("pymongo.cursor", "Cursor._refresh")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        collection = instance.collection
        signature = ".".join([collection.full_name, "cursor.refresh"])
        with capture_span(signature, span_type="db", span_subtype="mongodb", span_action="query"):
            return wrapped(*args, **kwargs)
