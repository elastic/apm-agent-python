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

import functools
import logging
import os

from elasticapm.traces import execution_context
from elasticapm.utils import wrapt

logger = logging.getLogger("elasticapm.instrument")


class AbstractInstrumentedModule(object):
    name = None
    mutates_unsampled_arguments = False

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
        if hasattr(instance, "__class__") and hasattr(instance.__class__, "__name__"):
            wrapped_name.append(instance.__class__.__name__)

        if hasattr(wrapped, "__name__"):
            wrapped_name.append(wrapped.__name__)
        elif fallback_method:
            attribute = fallback_method.split(".")
            if len(attribute) == 2:
                wrapped_name.append(attribute[1])

        return ".".join(wrapped_name)

    def get_instrument_list(self):
        return self.instrument_list

    def instrument(self):
        if self.instrumented:
            return

        skip_env_var = "SKIP_INSTRUMENT_" + str(self.name.upper())
        if skip_env_var in os.environ:
            logger.debug("Skipping instrumentation of %s. %s is set.", self.name, skip_env_var)
            return
        try:
            instrument_list = self.get_instrument_list()
            skipped_modules = set()
            instrumented_methods = []

            for module, method in instrument_list:
                try:
                    # Skip modules we already failed to load
                    if module in skipped_modules:
                        continue
                    # We jump through hoop here to get the original
                    # `module`/`method` in the call to `call_if_sampling`
                    parent, attribute, original = wrapt.resolve_path(module, method)
                    self.originals[(module, method)] = original
                    wrapper = wrapt.FunctionWrapper(original, functools.partial(self.call_if_sampling, module, method))
                    wrapt.apply_patch(parent, attribute, wrapper)
                    instrumented_methods.append((module, method))
                except ImportError:
                    # Could not import module
                    logger.debug("Skipping instrumentation of %s. Module %s not found", self.name, module)

                    # Keep track of modules we couldn't load so we don't
                    # try to instrument anything in that module again
                    skipped_modules.add(module)
                except AttributeError as ex:
                    # Could not find thing in module
                    logger.debug("Skipping instrumentation of %s.%s: %s", module, method, ex)
            if instrumented_methods:
                logger.debug("Instrumented %s, %s", self.name, ", ".join(".".join(m) for m in instrumented_methods))

        except ImportError as ex:
            logger.debug("Skipping instrumentation of %s. %s", self.name, ex)
        self.instrumented = True

    def uninstrument(self):
        if not self.instrumented or not self.originals:
            return
        uninstrumented_methods = []
        for module, method in self.get_instrument_list():
            if (module, method) in self.originals:
                parent, attribute, wrapper = wrapt.resolve_path(module, method)
                wrapt.apply_patch(parent, attribute, self.originals[(module, method)])
                uninstrumented_methods.append((module, method))
        if uninstrumented_methods:
            logger.debug("Uninstrumented %s, %s", self.name, ", ".join(".".join(m) for m in uninstrumented_methods))
        self.instrumented = False
        self.originals = {}

    def call_if_sampling(self, module, method, wrapped, instance, args, kwargs):
        transaction = execution_context.get_transaction()
        if not transaction:
            return wrapped(*args, **kwargs)
        elif not transaction.is_sampled:
            args, kwargs = self.mutate_unsampled_call_args(module, method, wrapped, instance, args, kwargs, transaction)
            return wrapped(*args, **kwargs)
        else:
            return self.call(module, method, wrapped, instance, args, kwargs)

    def mutate_unsampled_call_args(self, module, method, wrapped, instance, args, kwargs, transaction):
        """
        Method called for unsampled wrapped calls. This can e.g. be used to add traceparent headers to the
        underlying http call for HTTP instrumentations.

        :param module:
        :param method:
        :param wrapped:
        :param instance:
        :param args:
        :param kwargs:
        :param transaction:
        :return:
        """
        return args, kwargs

    def call(self, module, method, wrapped, instance, args, kwargs):
        """
        Wrapped call. This method should gather all necessary data, then call `wrapped` in a `capture_span` context
        manager.

        :param module: Name of the wrapped module
        :param method: Name of the wrapped method/function
        :param wrapped: the wrapped method/function object
        :param instance: the wrapped instance
        :param args: arguments to the wrapped method/function
        :param kwargs: keyword arguments to the wrapped method/function
        :return: the result of calling the wrapped method/function
        """
        raise NotImplementedError
