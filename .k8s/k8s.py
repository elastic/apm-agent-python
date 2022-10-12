#!/usr/bin/python
import click
import utils
from kubernetes.client.rest import ApiException
from kubernetes import client, config, watch


def results(framework, version, namespace):
    """Given the python and framework tuples then gather the results when the jobs have finished"""
    config.load_kube_config()
    with client.ApiClient() as api_client:
        api_instance = client.BatchV1Api(api_client)
        try:
            ## TODO: label selector to be specifc!
            label_selector = f'repo=apm-agent-python,type=unit-test'
            result = api_instance.list_namespaced_job(namespace, label_selector=label_selector)

            click.echo(click.style(f"There are {len(result.items)} jobs running ...", fg='yellow'))
            # If there are jobs for the given selector
            if len(result.items) > 0:
                jobs = [obj.metadata.name for obj in result.items]
                collect_logs(jobs, label_selector, namespace)
                click.echo(click.style(f"Results are now ready...", fg='green'))
        except ApiException as e:
            raise Exception("Exception when calling BatchV1Api->list_namespaced_job: %s\n" % e)


def collect_logs(jobs, label_selector, namespace):
    """Given the K8s jobs then gather the results and logs"""
    w = watch.Watch()
    failed_jobs = []
    click.echo(click.style("Waiting for jobs to complete...", fg='yellow'))
    for event in w.stream(
        client.BatchV1Api().list_namespaced_job,
        namespace=namespace,
        label_selector=label_selector,
        timeout_seconds=0
    ):
        o = event["object"]

        if o.status.succeeded:
            click.echo(click.style(f"{o.metadata.name} completed", fg='green'))
            gather_logs(o, namespace)
            jobs.remove(o.metadata.name)
            if len(jobs) == 0:
                w.stop()
                if len(failed_jobs) > 0:
                    raise Exception("Failed jobs " + str(failed_jobs))
            else:
                click.echo(click.style(f"There are some jobs still running {str(jobs)}", fg='yellow'))

        if not o.status.active and o.status.failed:
            click.echo(click.style(f"{o.metadata.name} failed", fg='red'))
            gather_logs(o, namespace)
            jobs.remove(o.metadata.name)
            failed_jobs.append(o.metadata.name)
            if len(jobs) == 0:
                w.stop()
                raise Exception("Failed jobs " + str(failed_jobs))
            else:
                click.echo(click.style(f"There are some jobs still running {str(jobs)}", fg='yellow'))


def gather_logs(job, namespace):
    try:
        pods_list = get_pods_for_job(job, namespace)

        if pods_list == None or len(pods_list.items) == 0:
            ## TODO something went wrong
            return

        # NOTE: it assumes 1 container in the pod
        pod_name = pods_list.items[0].metadata.name

        # Gather logs
        export_logs(job.metadata.name, pod_name, namespace)
    except ApiException as e:
        print("Exception when calling CoreV1Api->read_namespaced_pod_log: %s\n" % e)


def export_logs(job_name, pod_name, namespace):
    try:
        api_instance = client.CoreV1Api()
        pod_log_response = api_instance.read_namespaced_pod_log(name=pod_name, namespace=namespace, _return_http_data_only=True, _preload_content=False)
        pod_log = pod_log_response.data.decode("utf-8")
        with open(f'{utils.Constants.BUILD}/{job_name}.log', 'w') as f:
            f.write(pod_log)
    except ApiException as e:
        print("Exception when calling CoreV1Api->read_namespaced_pod_log: %s\n" % e)


def get_pods_for_job(job, namespace):
    try:
        api_instance = client.CoreV1Api()
        controllerUid = job.spec.template.metadata.labels["controller-uid"]
        pod_label_selector = "controller-uid=" + controllerUid
        return api_instance.list_namespaced_pod(namespace=namespace, label_selector=pod_label_selector, timeout_seconds=10)
    except ApiException as e:
        print("Exception when calling CoreV1Api->read_namespaced_pod_log: %s\n" % e)
        return None
