# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from . import testgrpc_pb2 as test__pb2


class TestServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.GetServerResponse = channel.unary_unary(
                '/test.TestService/GetServerResponse',
                request_serializer=test__pb2.Message.SerializeToString,
                response_deserializer=test__pb2.MessageResponse.FromString,
                )
        self.GetServerResponseAbort = channel.unary_unary(
                '/test.TestService/GetServerResponseAbort',
                request_serializer=test__pb2.Message.SerializeToString,
                response_deserializer=test__pb2.MessageResponse.FromString,
                )
        self.GetServerResponseUnavailable = channel.unary_unary(
                '/test.TestService/GetServerResponseUnavailable',
                request_serializer=test__pb2.Message.SerializeToString,
                response_deserializer=test__pb2.MessageResponse.FromString,
                )
        self.GetServerResponseException = channel.unary_unary(
                '/test.TestService/GetServerResponseException',
                request_serializer=test__pb2.Message.SerializeToString,
                response_deserializer=test__pb2.MessageResponse.FromString,
                )


class TestServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def GetServerResponse(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetServerResponseAbort(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetServerResponseUnavailable(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetServerResponseException(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_TestServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'GetServerResponse': grpc.unary_unary_rpc_method_handler(
                    servicer.GetServerResponse,
                    request_deserializer=test__pb2.Message.FromString,
                    response_serializer=test__pb2.MessageResponse.SerializeToString,
            ),
            'GetServerResponseAbort': grpc.unary_unary_rpc_method_handler(
                    servicer.GetServerResponseAbort,
                    request_deserializer=test__pb2.Message.FromString,
                    response_serializer=test__pb2.MessageResponse.SerializeToString,
            ),
            'GetServerResponseUnavailable': grpc.unary_unary_rpc_method_handler(
                    servicer.GetServerResponseUnavailable,
                    request_deserializer=test__pb2.Message.FromString,
                    response_serializer=test__pb2.MessageResponse.SerializeToString,
            ),
            'GetServerResponseException': grpc.unary_unary_rpc_method_handler(
                    servicer.GetServerResponseException,
                    request_deserializer=test__pb2.Message.FromString,
                    response_serializer=test__pb2.MessageResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'test.TestService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class TestService(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def GetServerResponse(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/test.TestService/GetServerResponse',
            test__pb2.Message.SerializeToString,
            test__pb2.MessageResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetServerResponseAbort(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/test.TestService/GetServerResponseAbort',
            test__pb2.Message.SerializeToString,
            test__pb2.MessageResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetServerResponseUnavailable(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/test.TestService/GetServerResponseUnavailable',
            test__pb2.Message.SerializeToString,
            test__pb2.MessageResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetServerResponseException(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/test.TestService/GetServerResponseException',
            test__pb2.Message.SerializeToString,
            test__pb2.MessageResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
