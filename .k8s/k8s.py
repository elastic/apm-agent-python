#!/usr/bin/python
import click
from time import sleep
from kubernetes.client.rest import ApiException
import kubernetes


def results(framework, version, namespace):
    """Given the python and framework then gather the results when the jobs have finished"""
    click.echo(click.style(f"TBC framework={framework} version={version}", fg='blue'))

    ## Loop for each version/framework and activiley look for whether it has finished and if so the
    #for ver in version:
    #    for fram in framework:
    # Configs can be set in Configuration class directly or using helper
    # utility. If no argument provided, the config will be loaded from
    # default location.
    kubernetes.config.load_kube_config()
    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.BatchV1Api(api_client)
        try:
            label_selector = f'repo=apm-agent-python,type=unit-test'
            result = api_instance.list_namespaced_job(namespace, label_selector=label_selector)
            #print(api_response)
            print(len(result.items))
            for r in result.items:
                print(r.metadata.name)
                get_job_status(api_instance, r.metadata.name, namespace)
        except ApiException as e:
            print("Exception when calling BatchV1Api->list_namespaced_job: %s\n" % e)


def get_job_status(api_instance, job_name, namespace):
    job_completed = False
    while not job_completed:
        api_response = api_instance.read_namespaced_job_status(
            name=job_name,
            namespace=namespace)
        if api_response.status.succeeded is not None or \
                api_response.status.failed is not None:
            job_completed = True
        sleep(1)
        print('.', end=" ")
        #print("Job status='%s'" % str(api_response.status))
    print("Job '%s' finished" % str(job_name))

