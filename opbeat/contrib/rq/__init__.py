def register_opbeat(client, worker):
    """Given a Opbeat client and an RQ worker, registers exception handlers
    with the worker so exceptions are logged to Opbeat.

    E.g.:

    from opbeat.contrib.django.models import client
    from opbeat.contrib.rq import register_opbeat
    
    worker = Worker(map(Queue, listen))
    register_opbeat(client, worker)
    worker.work()

    """
    def send_to_opbeat(job, *exc_info):
        client.capture_exception(
            exc_info=exc_info,
            extra={
                'job_id': job.id,
                'func': job.func_name,
                'args': job.args,
                'kwargs': job.kwargs,
                'description': job.description,
            }
        )

    worker.push_exc_handler(send_to_opbeat)
