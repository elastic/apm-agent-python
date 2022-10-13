#!/usr/bin/python
import click
from datetime import datetime, timezone
import utils
from kubernetes.client.rest import ApiException
from kubernetes import client, config, watch


def results(framework, version, namespace, git_username):
    """Given the python and framework tuples then gather the results when the jobs have finished"""
    config.load_kube_config()
    with client.ApiClient() as api_client:
        api_instance = client.BatchV1Api(api_client)
        try:
            label_selector = f'repo=apm-agent-python,type=unit-test,user.repo={git_username}'
            result = api_instance.list_namespaced_job(namespace, label_selector=label_selector)

            click.echo(click.style(f"There are {len(result.items)} jobs running ...", fg='yellow'))
            # If there are jobs for the given selector
            if len(result.items) > 0:
                jobs = [obj.metadata.name for obj in result.items]
                results = collect_logs(jobs, label_selector, namespace)
                click.echo(click.style(f"Results are now ready...", fg='green'))
                return results
        except ApiException as e:
            raise Exception("Exception when calling BatchV1Api->list_namespaced_job: %s\n" % e)


def collect_logs(jobs, label_selector, namespace):
    """Given the K8s jobs then gather the results and logs"""
    w = watch.Watch()
    running_jobs = jobs.copy()
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
            try:
                running_jobs.remove(o.metadata.name)
            except ValueError as e:
                # in some cases the job is not in the list ??
                click.echo(click.style(f"\t\t{o.metadata.name} could not be found in the running jobs. {running_jobs} jobs are running", fg='red'))
            duration = get_job_duration_time(o)
            click.echo(click.style(f"\t{o.metadata.name} completed [took {duration} seconds]. There are {len(running_jobs)} jobs running", fg='green'))
            gather_logs(o, namespace)
            if len(running_jobs) == 0:
                w.stop()
                return {
                  "jobs": jobs,
                  "failed": failed_jobs
                }

        if not o.status.active and o.status.failed:
            try:
                running_jobs.remove(o.metadata.name)
            except ValueError as e:
                # in some cases the job is not in the list ??
                click.echo(click.style(f"\t\t{o.metadata.name} could not be found in the running jobs. {running_jobs} jobs are running", fg='red'))
            failed_jobs.append(o.metadata.name)
            duration = get_job_duration_time(o)
            click.echo(click.style(f"\t{o.metadata.name} failed [took {duration} seconds]. There are {len(running_jobs)} jobs running", fg='red'))
            gather_logs(o, namespace)
            if len(running_jobs) == 0:
                w.stop()
                return {
                  "jobs": jobs,
                  "failed": failed_jobs
                }


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

        # Gather junit report if any
        # Required to use a PVC or similar since
        # cannot exec into a container in a completed pod; current phase is Succeeded
        #copy_test_results(pod_name, namespace)
    except ApiException as e:
        ## TODO: report the error?
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


def copy_test_results(pod_name, namespace):
    """Given the pod_name then copy the test results using the k8s CLI"""
    location = f'{utils.Constants.BUILD}/{pod_name}.xml'
    command = f'kubectl cp {pod_name}:/tmp/python-agent-junit.xml {location} -n {namespace}'
    utils.runCommand(command)


def get_pods_for_job(job, namespace):
    try:
        api_instance = client.CoreV1Api()
        controllerUid = job.spec.template.metadata.labels["controller-uid"]
        pod_label_selector = "controller-uid=" + controllerUid
        return api_instance.list_namespaced_pod(namespace=namespace, label_selector=pod_label_selector, timeout_seconds=10)
    except ApiException as e:
        print("Exception when calling CoreV1Api->read_namespaced_pod_log: %s\n" % e)
        return None


def get_job_duration_time(job):
    if job.status.completion_time:
        return job.status.completion_time - job.status.start_time
    # The completion time is only set when the job finishes successfully.
    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1JobStatus.md
    return datetime.now(timezone.utc) - job.status.start_time.astimezone(timezone.utc)
