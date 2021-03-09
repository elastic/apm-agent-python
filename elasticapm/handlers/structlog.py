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

from elasticapm import get_client
from elasticapm.traces import execution_context


def structlog_processor(logger, method_name, event_dict):
    """
    Add three new entries to the event_dict for any processed events:

    * transaction.id
    * trace.id
    * span.id

    Only adds non-None IDs.

    :param logger:
        Unused (logger instance in structlog)
    :param method_name:
        Unused (wrapped method_name)
    :param event_dict:
        Event dictionary for the event we're processing
    :return:
        `event_dict`, with three new entries.
    """
    transaction = execution_context.get_transaction()
    if transaction:
        event_dict["transaction.id"] = transaction.id
    client = get_client()
    if client:
        event_dict["service.name"] = client.config.service_name
        event_dict["event.dataset"] = f"{client.config.service_name}.log"
    if transaction and transaction.trace_parent:
        event_dict["trace.id"] = transaction.trace_parent.trace_id
    span = execution_context.get_span()
    if span and span.id:
        event_dict["span.id"] = span.id
    return event_dict
