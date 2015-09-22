from opbeat.instrumentation import register


def instrument():
    for obj in register.get_instrumentation_objects():
        obj.instrument()
