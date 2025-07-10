#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
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


from __future__ import absolute_import

import logging

import wrapt

from elasticapm import get_client
from elasticapm.traces import execution_context


@wrapt.decorator
def log_record_factory(wrapped, instance, args, kwargs):
    """
    Decorator, designed to wrap the python log record factory (fetched by
    logging.getLogRecordFactory), adding the same custom attributes as in
    the LoggingFilter provided above.

    :return:
        LogRecord object, with custom attributes for APM tracing fields
    """
    record = wrapped(*args, **kwargs)
    return _add_attributes_to_log_record(record)


def _add_attributes_to_log_record(record):
    """
    Add custom attributes for APM tracing fields to a LogRecord object

    :param record: LogRecord object
    :return: Updated LogRecord object with new APM tracing fields
    """
    transaction = execution_context.get_transaction()

    transaction_id = transaction.id if transaction else None
    record.elasticapm_transaction_id = transaction_id

    trace_id = transaction.trace_parent.trace_id if transaction and transaction.trace_parent else None
    record.elasticapm_trace_id = trace_id

    span = execution_context.get_span()
    span_id = span.id if span else None
    record.elasticapm_span_id = span_id

    client = get_client()
    service_name = client.config.service_name if client else None
    record.elasticapm_service_name = service_name

    service_environment = client.config.environment if client else None
    record.elasticapm_service_environment = service_environment

    record.elasticapm_labels = {
        "transaction.id": transaction_id,
        "trace.id": trace_id,
        "span.id": span_id,
        "service.name": service_name,
        "service.environment": service_environment,
    }

    return record


class Formatter(logging.Formatter):
    """
    Custom formatter to automatically append the elasticapm format string,
    as well as ensure that LogRecord objects actually have the required fields
    (so as to avoid errors which could occur for logs before we override the
    LogRecordFactory):

        formatstring = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        formatstring = formatstring + " | elasticapm " \
                                      "transaction.id=%(elasticapm_transaction_id)s " \
                                      "trace.id=%(elasticapm_trace_id)s " \
                                      "span.id=%(elasticapm_span_id)s"
    """

    def __init__(self, fmt=None, datefmt=None, style="%") -> None:
        if fmt is None:
            fmt = "%(message)s"
        fmt = (
            fmt + " | elasticapm "
            "transaction.id=%(elasticapm_transaction_id)s "
            "trace.id=%(elasticapm_trace_id)s "
            "span.id=%(elasticapm_span_id)s"
        )
        super(Formatter, self).__init__(fmt=fmt, datefmt=datefmt, style=style)

    def format(self, record):
        if not hasattr(record, "elasticapm_transaction_id"):
            record.elasticapm_transaction_id = None
            record.elasticapm_trace_id = None
            record.elasticapm_span_id = None
            record.elasticapm_service_name = None
            record.elasticapm_service_environment = None
        return super(Formatter, self).format(record=record)

    def formatTime(self, record, datefmt=None):
        if not hasattr(record, "elasticapm_transaction_id"):
            record.elasticapm_transaction_id = None
            record.elasticapm_trace_id = None
            record.elasticapm_span_id = None
            record.elasticapm_service_name = None
            record.elasticapm_service_environment = None
        return super(Formatter, self).formatTime(record=record, datefmt=datefmt)
