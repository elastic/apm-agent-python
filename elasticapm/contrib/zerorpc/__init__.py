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


import inspect

from elasticapm.base import Client


class Middleware(object):
    """ElasticAPM middleware for ZeroRPC.

    >>> elasticapm = Middleware(service_name='..', secret_token='...')
    >>> zerorpc.Context.get_instance().register_middleware(elasticapm)

    Exceptions detected server-side in ZeroRPC will be submitted to the apm server (and
    propagated to the client as well).
    """

    def __init__(self, hide_zerorpc_frames=True, client=None, **kwargs):
        """Create a middleware object that can be injected in a ZeroRPC server.

        - hide_zerorpc_frames: modify the exception stacktrace to remove the
                               internal zerorpc frames (True by default to make
                               the stacktrace as readable as possible);
        - client: use an existing raven.Client object, otherwise one will be
                  instantiated from the keyword arguments.

        """
        self._elasticapm_client = client or Client(**kwargs)
        self._hide_zerorpc_frames = hide_zerorpc_frames

    def server_inspect_exception(self, req_event, rep_event, task_ctx, exc_info):
        """Called when an exception has been raised in the code run by ZeroRPC"""

        # Hide the zerorpc internal frames for readability, for a REQ/REP or
        # REQ/STREAM server the frames to hide are:
        # - core.ServerBase._async_task
        # - core.Pattern*.process_call
        # - core.DecoratorBase.__call__
        #
        # For a PUSH/PULL or PUB/SUB server the frame to hide is:
        # - core.Puller._receiver
        if self._hide_zerorpc_frames:
            traceback = exc_info[2]
            while traceback:
                zerorpc_frame = traceback.tb_frame
                zerorpc_frame.f_locals["__traceback_hide__"] = True
                frame_info = inspect.getframeinfo(zerorpc_frame)
                # Is there a better way than this (or looking up the filenames
                # or hardcoding the number of frames to skip) to know when we
                # are out of zerorpc?
                if frame_info.function == "__call__" or frame_info.function == "_receiver":
                    break
                traceback = traceback.tb_next

        self._elasticapm_client.capture_exception(exc_info, extra=task_ctx, handled=False)
