import functools
import logging

from elasticapm.traces import get_transaction
from elasticapm.utils import wrapt

logger = logging.getLogger(__name__)


# We have our own `BoundFunctionWrapper` and `FunctionWrapper` here because
# we want them to be able to now about `module` and `method` and supply it in
# the call to the wrapper.

class OriginalNamesBoundFunctionWrapper(wrapt.BoundFunctionWrapper):

    def __init__(self, *args, **kwargs):
        super(OriginalNamesBoundFunctionWrapper, self).__init__(*args, **kwargs)
        self._self_module = self._self_parent._self_module
        self._self_method = self._self_parent._self_method

    def __call__(self, *args, **kwargs):
        # If enabled has been specified, then evaluate it at this point
        # and if the wrapper is not to be executed, then simply return
        # the bound function rather than a bound wrapper for the bound
        # function. When evaluating enabled, if it is callable we call
        # it, otherwise we evaluate it as a boolean.

        if self._self_enabled is not None:
            if callable(self._self_enabled):
                if not self._self_enabled():
                    return self.__wrapped__(*args, **kwargs)
            elif not self._self_enabled:
                return self.__wrapped__(*args, **kwargs)

        # We need to do things different depending on whether we are
        # likely wrapping an instance method vs a static method or class
        # method.

        if self._self_binding == 'function':
            if self._self_instance is None:
                # This situation can occur where someone is calling the
                # instancemethod via the class type and passing the instance
                # as the first argument. We need to shift the args before
                # making the call to the wrapper and effectively bind the
                # instance to the wrapped function using a partial so the
                # wrapper doesn't see anything as being different.

                if not args:
                    raise TypeError(
                        'missing 1 required positional argument')

                instance, args = args[0], args[1:]
                wrapped = functools.partial(self.__wrapped__, instance)
                return self._self_wrapper(self._self_module,
                                          self._self_method,
                                          wrapped, instance, args, kwargs)

            return self._self_wrapper(self._self_module,
                                      self._self_method,
                                      self.__wrapped__, self._self_instance,
                                      args, kwargs)

        else:
            # As in this case we would be dealing with a classmethod or
            # staticmethod, then _self_instance will only tell us whether
            # when calling the classmethod or staticmethod they did it via an
            # instance of the class it is bound to and not the case where
            # done by the class type itself. We thus ignore _self_instance
            # and use the __self__ attribute of the bound function instead.
            # For a classmethod, this means instance will be the class type
            # and for a staticmethod it will be None. This is probably the
            # more useful thing we can pass through even though we loose
            # knowledge of whether they were called on the instance vs the
            # class type, as it reflects what they have available in the
            # decoratored function.

            instance = getattr(self.__wrapped__, '__self__', None)

            return self._self_wrapper(self._self_module,
                                      self._self_method,
                                      self.__wrapped__, instance, args,
                                      kwargs)


class OriginalNamesFunctionWrapper(wrapt.FunctionWrapper):

    __bound_function_wrapper__ = OriginalNamesBoundFunctionWrapper

    def __init__(self, wrapped, wrapper, module, method):
        super(OriginalNamesFunctionWrapper, self).__init__(wrapped, wrapper)
        self._self_module = module
        self._self_method = method

    def __call__(self, *args, **kwargs):
        # If enabled has been specified, then evaluate it at this point
        # and if the wrapper is not to be executed, then simply return
        # the bound function rather than a bound wrapper for the bound
        # function. When evaluating enabled, if it is callable we call
        # it, otherwise we evaluate it as a boolean.

        if self._self_enabled is not None:
            if callable(self._self_enabled):
                if not self._self_enabled():
                    return self.__wrapped__(*args, **kwargs)
            elif not self._self_enabled:
                return self.__wrapped__(*args, **kwargs)

        # This can occur where initial function wrapper was applied to
        # a function that was already bound to an instance. In that case
        # we want to extract the instance from the function and use it.

        if self._self_binding == 'function':
            if self._self_instance is None:
                instance = getattr(self.__wrapped__, '__self__', None)
                if instance is not None:
                    return self._self_wrapper(self._self_module,
                                              self._self_method,
                                              self.__wrapped__, instance,
                                              args, kwargs)

        # This is generally invoked when the wrapped function is being
        # called as a normal function and is not bound to a class as an
        # instance method. This is also invoked in the case where the
        # wrapped function was a method, but this wrapper was in turn
        # wrapped using the staticmethod decorator.

        return self._self_wrapper(self._self_module,
                                  self._self_method,
                                  self.__wrapped__, self._self_instance,
                                  args, kwargs)


class AbstractInstrumentedModule(object):
    name = None

    instrument_list = [
        # List of (module, method) pairs to instrument. E.g.:
        # ("requests.sessions", "Session.send"),
    ]

    def __init__(self):
        """

        :param client: elasticapm.base.Client
        """
        self.originals = {}
        self.instrumented = False

        assert self.name is not None

    def get_wrapped_name(self, wrapped, instance, fallback_method=None):
        wrapped_name = []
        if hasattr(instance, '__class__') and hasattr(instance.__class__, '__name__'):
            wrapped_name.append(instance.__class__.__name__)

        if hasattr(wrapped, '__name__'):
            wrapped_name.append(wrapped.__name__)
        elif fallback_method:
            attribute = fallback_method.split('.')
            if len(attribute) == 2:
                wrapped_name.append(attribute[1])

        return ".".join(wrapped_name)

    def get_instrument_list(self):
        return self.instrument_list

    def instrument(self):
        if self.instrumented:
            return

        try:
            instrument_list = self.get_instrument_list()
            skipped_modules = set()

            for module, method in instrument_list:
                try:
                    # Skip modules we already failed to load
                    if module in skipped_modules:
                        continue
                    # We jump through hoop here to get the original
                    # `module`/`method` in the call to `call_if_sampling`
                    parent, attribute, original = wrapt.resolve_path(module, method)
                    self.originals[(module, method)] = original
                    wrapper = OriginalNamesFunctionWrapper(
                        original,
                        self.call_if_sampling,
                        module,
                        method
                    )
                    wrapt.apply_patch(parent, attribute, wrapper)
                except ImportError:
                    # Could not import module
                    logger.debug("Skipping instrumentation of %s."
                                 " Module %s not found",
                                 self.name, module)

                    # Keep track of modules we couldn't load so we don't
                    # try to instrument anything in that module again
                    skipped_modules.add(module)
                except AttributeError as ex:
                    # Could not find thing in module
                    logger.debug("Skipping instrumentation of %s.%s: %s",
                                 module, method, ex)

        except ImportError as ex:
            logger.debug("Skipping instrumentation of %s. %s",
                         self.name, ex)
        self.instrumented = True

    def uninstrument(self):
        if not self.instrumented or not self.originals:
            return
        for module, method in self.get_instrument_list():
            if (module, method) in self.originals:
                parent, attribute, wrapper = wrapt.resolve_path(module, method)
                wrapt.apply_patch(parent, attribute, self.originals[(module, method)])
        self.instrumented = False
        self.originals = {}

    def call_if_sampling(self, module, method, wrapped, instance, args, kwargs):
        if not get_transaction():
            return wrapped(*args, **kwargs)
        else:
            return self.call(module, method, wrapped, instance, args, kwargs)

    def call(self, module, method, wrapped, instance, args, kwargs):
        raise NotImplemented
