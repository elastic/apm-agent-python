import warnings

from elasticapm.transport.http import AsyncTransport as AsyncUrllib3Transport  # noqa F401
from elasticapm.transport.http import Transport as Urllib3Transport  # noqa F401

warnings.warn(
    "The elasticapm.transport.http_urllib3 module has been renamed to elasticapm.transport.http", DeprecationWarning
)
