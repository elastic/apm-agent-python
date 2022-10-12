#!/usr/bin/python
import click
from time import sleep
from kubernetes.client.rest import ApiException
from kubernetes import client, config, watch


def results(framework, version, namespace):
    """Given the python and framework then gather the results when the jobs have finished"""
    click.echo(click.style(f"TBC framework={framework} version={version}", fg='blue'))
    config.load_kube_config()
    with client.ApiClient() as api_client:
        api_instance = client.BatchV1Api(api_client)
        try:
            ## TOOD: label selector to be specifc!
            label_selector = f'repo=apm-agent-python,type=unit-test'
            result = api_instance.list_namespaced_job(namespace, label_selector=label_selector)
            if len(result.items) > 0:
                jobs = [obj.metadata.name for obj in result.items]
                wait_for(jobs, label_selector, namespace)
            click.echo(click.style(f"Results are now ready...", fg='green'))
        except ApiException as e:
            print("Exception when calling BatchV1Api->list_namespaced_job: %s\n" % e)


def wait_for(jobs, label_selector, namespace):
    w = watch.Watch()
    failed_jobs = []
    print(f"Waiting for jobs to complete... (label_selector={label_selector})\n")
    for event in w.stream(
        client.BatchV1Api().list_namespaced_job,
        namespace=namespace,
        label_selector=label_selector,
        timeout_seconds=0
    ):
        o = event["object"]

        if o.status.succeeded:
            print(f"{o.metadata.name} completed")
            print(f"debug {o.metadata}")
            gatherLogs(o.metadata.name, namespace)
            jobs.remove(o.metadata.name)
            if len(jobs) == 0:
                w.stop()
                if len(failed_jobs) > 0:
                    raise Exception("Failed jobs " + str(failed_jobs))
                return
            else:
                print("   There are some jobs still running " + str(jobs))

        if not o.status.active and o.status.failed:
            print(f"{o.metadata.name} failed")
            gatherLogs(o.metadata.name, namespace)
            jobs.remove(o.metadata.name)
            failed_jobs.append(o.metadata.name)
            if len(jobs) == 0:
                w.stop()
                raise Exception("Failed jobs " + str(failed_jobs))
            else:
                print("   There are some jobs still running " + str(jobs))


def gatherLogs(pod_name, namespace):
    try:
        api_instance = client.CoreV1Api()
        api_response = api_instance.read_namespaced_pod_log(name=pod_name, namespace=namespace)
        print(api_response)
    except ApiException as e:
        print(f'Found exception in reading the logs {e}')

def wait_for_job(framework, version, namespace):
    config.load_kube_config()
    w = watch.Watch()
    ## TODO: gather the list of jobs dynamically
    jobs = ['apm-agen-python-3-10-django-4-0', 'apm-agen-python-3-10-none', 'apm-agen-python-3-10-django-3-1', 'apm-agen-python-3-10-django-3-2']
    failed_jobs = []
    label_selector = f'repo=apm-agent-python,type=unit-test'
    print(f"Waiting for jobs to complete... (label_selector={label_selector})\n")
    for event in w.stream(
        client.BatchV1Api().list_namespaced_job,
        namespace=namespace,
        label_selector=label_selector,
        timeout_seconds=0
    ):
        o = event["object"]

        if o.status.succeeded:
            print(f"{o.metadata.name} completed")
            jobs.remove(o.metadata.name)
            if len(jobs) == 0:
                w.stop()
                if len(failed_jobs) > 0:
                    raise Exception("Failed jobs " + str(failed_jobs))
                return
            else:
                print("   There are some jobs still running " + str(jobs))

        if not o.status.active and o.status.failed:
            jobs.remove(o.metadata.name)
            failed_jobs.append(o.metadata.name)
            print(f"{o.metadata.name} failed")
            if len(jobs) == 0:
                w.stop()
                raise Exception("Failed jobs " + str(failed_jobs))
            else:
                print("   There are some jobs still running " + str(jobs))

