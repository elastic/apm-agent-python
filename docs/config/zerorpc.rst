Configuring ZeroRPC
===================

Setup
-----

The ZeroRPC integration comes as middleware for ZeroRPC. The middleware can be
configured like the original opbeat_python client (using keyword arguments) and
registered into ZeroRPC's context manager::

    import zerorpc

    from opbeat_python.contrib.zerorpc import OpbeatMiddleware

    sentry = OpbeatMiddleware(dsn='udp://public_key:secret_key@example.com:4242/1')
    zerorpc.Context.get_instance().register_middleware(sentry)

By default, the middleware will hide internal frames from ZeroRPC when it
submits exceptions to Opbeat. This behavior can be disabled by passing the
``hide_zerorpc_frames`` parameter to the middleware::

    sentry = OpbeatMiddleware(hide_zerorpc_frames=False, dsn='udp://public_key:secret_key@example.com:4242/1')

Caveats
-------

Since sending an exception to Opbeat will basically block your RPC call, you are
*strongly* advised to use the UDP server of Opbeat. In any cases, a cleaner and
long term solution would be to make opbeat_python requests to the Opbeat server
asynchronous.
