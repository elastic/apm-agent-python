from ..testapp.celery import app


@app.task()
def successful_task():
    return "OK"


@app.task()
def failing_task():
    raise ValueError('foo')
