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
import random
import re
import time
import timeit

from elasticapm.conf import constants
from elasticapm.conf.constants import SPAN, TRANSACTION
from elasticapm.utils import compat, encoding, get_name_from_func
from elasticapm.utils.disttracing import TraceParent, TracingOptions

__all__ = ("capture_span", "tag", "set_transaction_name", "set_custom_context", "set_user_context")

error_logger = logging.getLogger("elasticapm.errors")
logger = logging.getLogger("elasticapm.traces")

_time_func = timeit.default_timer


TAG_RE = re.compile('[.*"]')


try:
    from elasticapm.context.contextvars import execution_context
except ImportError:
    from elasticapm.context.threadlocal import execution_context


class Transaction(object):
    def __init__(self, tracer, transaction_type="custom", trace_parent=None, is_sampled=True):
        self.id = "%016x" % random.getrandbits(64)
        self.trace_parent = trace_parent
        self.timestamp, self.start_time = time.time(), _time_func()
        self.name = None
        self.duration = None
        self.result = None
        self.transaction_type = transaction_type
        self._tracer = tracer

        self.dropped_spans = 0
        self.context = {}
        self.tags = {}

        self.is_sampled = is_sampled
        self._span_counter = 0

    def end_transaction(self):
        self.duration = _time_func() - self.start_time

    def _begin_span(self, name, span_type, context=None, leaf=False, tags=None, parent_span_id=None):
        parent_span = execution_context.get_span()
        tracer = self._tracer
        if parent_span and parent_span.leaf:
            span = DroppedSpan(parent_span, leaf=True)
        elif tracer.max_spans and self._span_counter > tracer.max_spans - 1:
            self.dropped_spans += 1
            span = DroppedSpan(parent_span)
            self._span_counter += 1
        else:
            span = Span(
                transaction=self,
                name=name,
                span_type=span_type or "code.custom",
                context=context,
                leaf=leaf,
                tags=tags,
                parent_span_id=parent_span_id,
            )
            span.frames = tracer.frames_collector_func()
            span.parent = parent_span
            self._span_counter += 1
        execution_context.set_span(span)
        return span

    def begin_span(self, name, span_type, context=None, leaf=False, tags=None):
        """
        Begin a new span
        :param name: name of the span
        :param span_type: type of the span
        :param context: a context dict
        :param leaf: True if this is a leaf span
        :param tags: a flat string/string dict of tags
        :return: the Span object
        """
        return self._begin_span(name, span_type, context=context, leaf=leaf, tags=tags, parent_span_id=None)

    def end_span(self, skip_frames=0):
        span = execution_context.get_span()
        if span is None:
            raise LookupError()
        if isinstance(span, DroppedSpan):
            execution_context.set_span(span.parent)
            return

        span.duration = _time_func() - span.start_time

        if not self._tracer.span_frames_min_duration or span.duration >= self._tracer.span_frames_min_duration:
            span.frames = self._tracer.frames_processing_func(span.frames)[skip_frames:]
        else:
            span.frames = None
        execution_context.set_span(span.parent)
        self._tracer.queue_func(SPAN, span.to_dict())
        return span

    def ensure_parent_id(self):
        """If current trace_parent has no span_id, generate one, then return it

        This is used to generate a span ID which the RUM agent will use to correlate
        the RUM transaction with the backend transaction.
        """
        if self.trace_parent.span_id == self.id:
            self.trace_parent.span_id = "%016x" % random.getrandbits(64)
            logger.debug("Set parent id to generated %s", self.trace_parent.span_id)
        return self.trace_parent.span_id

    def tag(self, **tags):
        """
        Tag this transaction with one or multiple key/value tags. Both the values should be strings

            transaction_obj.tag(key1="value1", key2="value2")

        Note that keys will be dedotted, replacing dot (.), star (*) and double quote (") with an underscore (_)
        """
        for key in tags.keys():
            self.tags[TAG_RE.sub("_", compat.text_type(key))] = encoding.keyword_field(compat.text_type(tags[key]))

    def to_dict(self):
        self.context["tags"] = self.tags
        result = {
            "id": self.id,
            "trace_id": self.trace_parent.trace_id,
            "name": encoding.keyword_field(self.name or ""),
            "type": encoding.keyword_field(self.transaction_type),
            "duration": self.duration * 1000,  # milliseconds
            "result": encoding.keyword_field(str(self.result)),
            "timestamp": int(self.timestamp * 1000000),  # microseconds
            "sampled": self.is_sampled,
            "span_count": {"started": self._span_counter - self.dropped_spans, "dropped": self.dropped_spans},
        }
        if self.trace_parent:
            result["trace_id"] = self.trace_parent.trace_id
            # only set parent_id if this transaction isn't the root
            if self.trace_parent.span_id and self.trace_parent.span_id != self.id:
                result["parent_id"] = self.trace_parent.span_id
        if self.is_sampled:
            result["context"] = self.context
        return result


class Span(object):
    __slots__ = (
        "id",
        "transaction",
        "name",
        "type",
        "context",
        "leaf",
        "timestamp",
        "start_time",
        "duration",
        "parent",
        "parent_span_id",
        "frames",
        "tags",
    )

    def __init__(self, transaction, name, span_type, context=None, leaf=False, tags=None, parent_span_id=None):
        """
        Create a new Span

        :param transaction: transaction object that this span relates to
        :param name: Generic name of the span
        :param span_type: type of the span
        :param context: context dictionary
        :param leaf: is this span a leaf span?
        :param tags: a dict of tags
        :param parent_span_id: override of the span ID
        """
        self.start_time = _time_func()
        self.id = "%016x" % random.getrandbits(64)
        self.transaction = transaction
        self.name = name
        self.type = span_type
        self.context = context
        self.leaf = leaf
        # timestamp is bit of a mix of monotonic and non-monotonic time sources.
        # we take the (non-monotonic) transaction timestamp, and add the (monotonic) difference of span
        # start time and transaction start time. In this respect, the span timestamp is guaranteed to grow
        # monotonically with respect to the transaction timestamp
        self.timestamp = transaction.timestamp + (self.start_time - transaction.start_time)
        self.duration = None
        self.parent = None
        self.parent_span_id = parent_span_id
        self.frames = None
        self.tags = {}
        if tags:
            self.tag(**tags)

    def tag(self, **tags):
        """
        Tag this span with one or multiple key/value tags. Both the values should be strings

            span_obj.tag(key1="value1", key2="value2")

        Note that keys will be dedotted, replacing dot (.), star (*) and double quote (") with an underscore (_)
        """
        for key in tags.keys():
            self.tags[TAG_RE.sub("_", compat.text_type(key))] = encoding.keyword_field(compat.text_type(tags[key]))

    def to_dict(self):
        result = {
            "id": self.id,
            "transaction_id": self.transaction.id,
            "trace_id": self.transaction.trace_parent.trace_id,
            # use either the explicitly set parent_span_id, or the id of the parent, or finally the transaction id
            "parent_id": self.parent_span_id or (self.parent.id if self.parent else self.transaction.id),
            "name": encoding.keyword_field(self.name),
            "type": encoding.keyword_field(self.type),
            "timestamp": int(self.timestamp * 1000000),  # microseconds
            "duration": self.duration * 1000,  # milliseconds
        }
        if self.tags:
            if self.context is None:
                self.context = {}
            self.context["tags"] = self.tags
        if self.context:
            result["context"] = self.context
        if self.frames:
            result["stacktrace"] = self.frames
        return result


class DroppedSpan(object):
    __slots__ = ("leaf", "parent")

    def __init__(self, parent, leaf=False):
        self.parent = parent
        self.leaf = leaf


class Tracer(object):
    def __init__(
        self,
        frames_collector_func,
        frames_processing_func,
        queue_func,
        sample_rate=1.0,
        max_spans=0,
        span_frames_min_duration=None,
        ignore_patterns=None,
    ):
        self.max_spans = max_spans
        self.queue_func = queue_func
        self.frames_processing_func = frames_processing_func
        self.frames_collector_func = frames_collector_func
        self._ignore_patterns = [re.compile(p) for p in ignore_patterns or []]
        self._sample_rate = sample_rate
        if span_frames_min_duration in (-1, None):
            # both None and -1 mean "no minimum"
            self.span_frames_min_duration = None
        else:
            self.span_frames_min_duration = span_frames_min_duration / 1000.0

    def begin_transaction(self, transaction_type, trace_parent=None):
        """
        Start a new transactions and bind it in a thread-local variable

        :returns the Transaction object
        """
        if trace_parent:
            is_sampled = bool(trace_parent.trace_options.recorded)
        else:
            is_sampled = self._sample_rate == 1.0 or self._sample_rate > random.random()
        transaction = Transaction(self, transaction_type, trace_parent=trace_parent, is_sampled=is_sampled)
        if trace_parent is None:
            transaction.trace_parent = TraceParent(
                constants.TRACE_CONTEXT_VERSION,
                "%032x" % random.getrandbits(128),
                transaction.id,
                TracingOptions(recorded=is_sampled),
            )
        execution_context.set_transaction(transaction)
        return transaction

    def _should_ignore(self, transaction_name):
        for pattern in self._ignore_patterns:
            if pattern.search(transaction_name):
                return True
        return False

    def end_transaction(self, result=None, transaction_name=None):
        transaction = execution_context.get_transaction(clear=True)
        if transaction:
            transaction.end_transaction()
            if transaction.name is None:
                transaction.name = transaction_name if transaction_name is not None else ""
            if self._should_ignore(transaction.name):
                return
            if transaction.result is None:
                transaction.result = result
            self.queue_func(TRANSACTION, transaction.to_dict())
        return transaction


class capture_span(object):
    def __init__(self, name=None, span_type="code.custom", extra=None, skip_frames=0, leaf=False, tags=None):
        self.name = name
        self.type = span_type
        self.extra = extra
        self.skip_frames = skip_frames
        self.leaf = leaf
        self.tags = tags

    def __call__(self, func):
        self.name = self.name or get_name_from_func(func)

        @functools.wraps(func)
        def decorated(*args, **kwds):
            with self:
                return func(*args, **kwds)

        return decorated

    def __enter__(self):
        transaction = execution_context.get_transaction()
        if transaction and transaction.is_sampled:
            return transaction.begin_span(self.name, self.type, context=self.extra, leaf=self.leaf, tags=self.tags)

    def __exit__(self, exc_type, exc_val, exc_tb):
        transaction = execution_context.get_transaction()
        if transaction and transaction.is_sampled:
            try:
                transaction.end_span(self.skip_frames)
            except LookupError:
                logger.info("ended non-existing span %s of type %s", self.name, self.type)


def tag(**tags):
    """
    Tags current transaction. Both key and value of the tag should be strings.
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        error_logger.warning("Ignored tags %s. No transaction currently active.", ", ".join(tags.keys()))
    else:
        transaction.tag(**tags)


def set_transaction_name(name, override=True):
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    if transaction.name is None or override:
        transaction.name = name


def set_transaction_result(result, override=True):
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    if transaction.result is None or override:
        transaction.result = result


def set_context(data, key="custom"):
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    if callable(data) and transaction.is_sampled:
        data = data()

    # remove invalid characters from key names
    if not callable(data):  # if transaction wasn't sampled, data is still a callable here and can be ignored
        for k in list(data.keys()):
            if TAG_RE.search(k):
                data[TAG_RE.sub("_", k)] = data.pop(k)

    if key in transaction.context:
        transaction.context[key].update(data)
    else:
        transaction.context[key] = data


set_custom_context = functools.partial(set_context, key="custom")


def set_user_context(username=None, email=None, user_id=None):
    data = {}
    if username is not None:
        data["username"] = encoding.keyword_field(username)
    if email is not None:
        data["email"] = encoding.keyword_field(email)
    if user_id is not None:
        data["id"] = encoding.keyword_field(user_id)
    set_context(data, "user")
