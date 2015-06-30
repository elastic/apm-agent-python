from opbeat.instrumentation import register


def instrument(client):
    for obj in register.get_instrumentation_objects():
        obj.instrument(client)
