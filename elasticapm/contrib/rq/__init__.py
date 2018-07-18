def register_elasticapm(client, worker):
    """Given an ElasticAPM client and an RQ worker, registers exception handlers
    with the worker so exceptions are logged to the apm server.

    E.g.:

    from elasticapm.contrib.django.models import client
    from elasticapm.contrib.rq import register_elasticapm

    worker = Worker(map(Queue, listen))
    register_elasticapm(client, worker)
    worker.work()

    """

    def send_to_server(job, *exc_info):
        client.capture_exception(
            exc_info=exc_info,
            extra={
                "job_id": job.id,
                "func": job.func_name,
                "args": job.args,
                "kwargs": job.kwargs,
                "description": job.description,
            },
        )

    worker.push_exc_handler(send_to_server)
