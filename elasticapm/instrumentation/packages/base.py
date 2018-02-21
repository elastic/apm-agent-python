import functools
import logging
import os

from elasticapm.traces import get_transaction
from elasticapm.utils import wrapt

logger = logging.getLogger(__name__)


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

        skip_env_var = 'SKIP_INSTRUMENT_' + str(self.name.upper())
        if skip_env_var in os.environ:
            logger.debug("Skipping instrumentation of %s. %s is set.",
                         self.name, skip_env_var)
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
                    wrapper = wrapt.FunctionWrapper(
                        original,
                        functools.partial(self.call_if_sampling, module, method),
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
        transaction = get_transaction()
        if not transaction or not transaction.is_sampled:
            return wrapped(*args, **kwargs)
        else:
            return self.call(module, method, wrapped, instance, args, kwargs)

    def call(self, module, method, wrapped, instance, args, kwargs):
        raise NotImplemented
