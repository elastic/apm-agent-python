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
        with capture_span(signature, "db.mongodb.query", leaf=True):
            return wrapped(*args, **kwargs)


class PyMongoBulkInstrumentation(AbstractInstrumentedModule):
    name = "pymongo"

    instrument_list = [("pymongo.bulk", "BulkOperationBuilder.execute")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        collection = instance._BulkOperationBuilder__bulk.collection
        signature = ".".join([collection.full_name, "bulk.execute"])
        with capture_span(signature, "db.mongodb.query"):
            return wrapped(*args, **kwargs)


class PyMongoCursorInstrumentation(AbstractInstrumentedModule):
    name = "pymongo"

    instrument_list = [("pymongo.cursor", "Cursor._refresh")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        collection = instance.collection
        signature = ".".join([collection.full_name, "cursor.refresh"])
        with capture_span(signature, "db.mongodb.query"):
            return wrapped(*args, **kwargs)
