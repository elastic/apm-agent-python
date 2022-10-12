#!/usr/bin/python
import click
from jinja2 import Template
import k8s
import templates
import utils
from pathlib import Path
import shutil
import yaml


with open(utils.Constants.DEFAULT_TEMPLATE) as file_:
    defaultManifestTemplate = Template(file_.read())

with open(utils.Constants.MANIFEST_TEMPLATE) as file_:
    manifestTemplate = Template(file_.read())

with open(utils.Constants.FRAMEWORK_TEMPLATE) as file_:
    frameworkTemplate = Template(file_.read())

with open(utils.Constants.PYTHON_TEMPLATE) as file_:
    pythonTemplate = Template(file_.read())

with open(utils.Constants.SKAFFOLD_TEMPLATE) as file_:
    skaffoldTemplate = Template(file_.read())


@click.command('generate', short_help='Generate the Skaffold context')
@click.option('--default', '-d', show_default=True, default="python-3.10", help="Default python version")
@click.option('--exclude', '-e', show_default=True, default=".ci/.jenkins_exclude.yml", help="YAML file with the list of version/framework tuples that are excluded")
@click.option('--framework', '-f', show_default=True, default=".ci/.jenkins_framework.yml", help="YAML file with the list of frameworks")
@click.option('--version', '-v', show_default=True, default=".ci/.jenkins_python.yml", help="YAML file with the list of versions")
def generate(default, version, framework, exclude):
    """Generate the Skaffold files for the given python and frameworks."""
    # Read files
    with open(version, "r") as fp:
        versionFile = yaml.safe_load(fp)
    with open(framework, "r") as fp:
        frameworkFile = yaml.safe_load(fp)
    with open(exclude, "r") as fp:
        excludeFile = yaml.safe_load(fp)

    # Generate the generated folder
    Path(utils.Constants.GENERATED).mkdir(parents=True, exist_ok=False)

    click.echo(click.style("Generating kubernetes configuration on the fly...", fg='yellow'))

    # Generate profiles for the given python versions
    for ver in versionFile.get('PYTHON_VERSION'):
        templates.generateVersionProfiles(ver)

    # Generate profiles for the given python and framewok versions
    for ver in versionFile.get('PYTHON_VERSION'):
        for fra in frameworkFile.get('FRAMEWORK'):
            if not utils.isExcluded(ver, fra, excludeFile):
                templates.generateSkaffoldEntries(ver, fra)

    click.echo(click.style("Generating skaffold configuration on the fly...", fg='yellow'))

    # Generate skaffold with the default python version
    output = skaffoldTemplate.render(version=utils.getPythonVersion(default))
    with open(utils.Constants.GENERATED_SKAFFOLD, 'w') as f:
        f.write(output)

    # Aggregate all the skaffold files and converge (order matters!)
    filenames = [utils.Constants.GENERATED_SKAFFOLD, utils.Constants.GENERATED_PROFILE]
    with open('skaffold.yaml', 'w') as outfile:
        for fname in filenames:
            with open(fname) as infile:
                for line in infile:
                    outfile.write(line)

    click.echo(click.style("Copying dockerignore file...", fg='yellow'))
    # avoid exposing anything unrelated to the source code.
    shutil.copyfile('.k8s/.dockerignore', '.dockerignore')

    click.echo(click.style("Copying default yaml file...", fg='yellow'))
    # skaffold requires a default manifest ... this is the workaround for now.
    templates.generateDefaultManifest(default)


@click.command('build', short_help='Build the docker images')
@click.option('--version', '-v', multiple=True, help="Python version to be built")
@click.option('--repo', '-r', show_default=True, default="docker.elastic.co/beats-dev", help="Docker repository")
@click.option('--extra', '-x', help="Extra arguments for the skaffold tool.")
def build(version, repo, extra):
    """Build docker images that contain your workspace and publish them to the given Docker repository."""
    # Enable the skaffold profiles matching the given version, if any
    profilesFlag = '-p ' +','.join(version)  if version else ''
    defaultRepositoryFlag = f'--default-repo={repo}' if repo else ''
    extraFlag = f'{extra}' if extra else ''
    command = f'skaffold build {extraFlag} {defaultRepositoryFlag} --file-output={utils.Constants.GENERATED_TAGS} {profilesFlag}'
    utils.runCommand(command)


@click.command('test', short_help='Test support matrix')
@click.option('--framework', '-f', multiple=True, help="Framework to be tested.")
@click.option('--version', '-v', multiple=True, help="Python version to be tested.")
@click.option('--extra', '-x', help="Extra arguments for the skaffold tool.")
@click.option('--namespace', '-n', show_default=True, default="default", help="Run the in the specified namespace")
def test(framework, version, extra, namespace):
    """Run the test support matrix for the default version and frameworks or filtered by them."""
    ## TODO set the --label=user.repo=git-username
    deploy(framework, version, extra, namespace)
    k8s.results(framework, version, namespace)


@click.command('results', short_help='Query results')
@click.option('--framework', '-f', multiple=True, help="Framework to be tested.")
@click.option('--version', '-v', multiple=True, help="Python version to be tested.")
@click.option('--namespace', '-n', show_default=True, default="default", help="Run the in the specified namespace")
def results(framework, version, namespace):
    """Query the results for the given version and frameworks or filtered by them."""
    k8s.results(framework, version, namespace)


def deploy(framework, version, extra, namespace):
    """Given the python and framework then run the skaffold deployment"""
    # Enable the skaffold profiles matching the given framework and version, if any
    profilesFlag = '-p ' + ','.join(framework + version) if (framework or version) else ''
    extraFlag = f'{extra}' if extra else ''
    command = f'skaffold deploy {extraFlag} --build-artifacts={utils.Constants.GENERATED_TAGS} -n {namespace} {profilesFlag}'
    utils.runCommand(command)
