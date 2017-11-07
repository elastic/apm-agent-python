import threading

from elasticapm.instrumentation import register

_lock = threading.Lock()


def instrument():
    """
    Instruments all registered methods/functions with a wrapper
    """
    with _lock:
        for obj in register.get_instrumentation_objects():
            obj.instrument()


def uninstrument():
    """
    If present, removes instrumentation and replaces it with the original method/function
    """
    with _lock:
        for obj in register.get_instrumentation_objects():
            obj.uninstrument()
