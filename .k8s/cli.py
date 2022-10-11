#!/usr/bin/python
import click
from jinja2 import Template
import os
from pathlib import Path
import shutil
import subprocess
import yaml

# Variables
templatesLocation = '.k8s/templates'
generatedLocation = '.k8s/generated'

with open(f'{templatesLocation}/manifest.yaml.tmpl') as file_:
    manifestTemplate = Template(file_.read())

with open(f'{templatesLocation}/profile.yaml.tmpl') as file_:
    profileTemplate = Template(file_.read())


@click.group()
def cli():
    """This script enriches Skaffold to run the given commands in K8s for the matrix support."""
    pass


@cli.command('generate', short_help='Generate the Skaffold context')
@click.option('--exclude', '-e', show_default=True, default=".ci/.jenkins_exclude.yml", help="YAML file with the list of version/framework tuples that are excluded")
@click.option('--framework', '-f', show_default=True, default=".ci/.jenkins_framework.yml", help="YAML file with the list of frameworks")
@click.option('--version', '-v', show_default=True, default=".ci/.jenkins_python.yml", help="YAML file with the list of versions")
def generate(version, framework, exclude):
    """This script enriches Skaffold to run the given commands in K8s for the matrix support."""
    click.echo(click.style(f"generate(exclude={exclude} framework={framework} version={version})", fg='blue'))
    # Read files
    with open(version, "r") as fp:
        versionFile = yaml.safe_load(fp)
    with open(framework, "r") as fp:
        frameworkFile = yaml.safe_load(fp)
    with open(exclude, "r") as fp:
        excludeFile = yaml.safe_load(fp)

    click.echo(click.style("Generating kubernetes configuration on the fly...", fg='yellow'))
    for ver in versionFile.get('PYTHON_VERSION'):
        for fra in frameworkFile.get('FRAMEWORK'):
            if not isExcluded(ver, fra, excludeFile):
                generateSkaffold(ver, fra)

    click.echo(click.style("Generating skaffold configuration on the fly...", fg='yellow'))
    filenames = [f'{templatesLocation}/skaffold.yaml', f'{generatedLocation}/profiles.tmp']
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
    shutil.copyfile(f'{templatesLocation}/default.yaml', f'{generatedLocation}/default.yaml')


@cli.command('build', short_help='Build the docker images')
@click.option('--version', '-v', multiple=True, help="Python version to be built")
@click.option('--repo', '-r', show_default=True, default="docker.elastic.co/beats-dev", help="Docker repository")
@click.option('--extra', '-x', help="Extra arguments for the skaffold tool.")
def build(version, repo, extra):
    """Build docker images that contain your workspace and publish them to the given Docker repository."""
    # Enable the skaffold profiles matching the given version, if any
    profilesFlag = ''
    if version:
        profilesFlag = '-p ' +','.join(version)
    defaultRepositoryFlag = ''
    if repo:
        defaultRepositoryFlag = f'--default-repo={repo}'
    extraFlag = ''
    if extra:
        extraFlag = f'{extra}'
    command = f'skaffold build {extraFlag} {defaultRepositoryFlag} --file-output={generatedLocation}/tags.json {profilesFlag}'
    runCommand(command)


@cli.command('test', short_help='Test support matrix')
@click.option('--framework', '-f', multiple=True, help="Framework to be tested.")
@click.option('--version', '-v', multiple=True, help="Python version to be tested.")
@click.option('--extra', '-x', help="Extra arguments for the skaffold tool.")
def test(framework, version, extra):
    """Run the test support matrix for the default version and frameworks or filtered by them."""
    click.echo(click.style(f"framework={framework} version={version}", fg='blue'))
    deploy(framework, version, extra)


def deploy(framework, version, extra):
    # Enable the skaffold profiles matching the given framework and version, if any
    profiles = ''
    if framework or version:
        profiles = '-p ' + ','.join(framework + version)
    click.echo(click.style(f"TBC skaffold deploy {extra} {profiles} ", fg='red'))



def generateSkaffold(version, framework):
    """Given the python and framework then generate the k8s manifest and skaffold profile"""
    # print(" - generating skaffold for " + version + " and " + framework)
    pythonVersion = getPythonVersion(version)
    frameworkName = getFrameworkName(framework)

    # Render the template
    output = manifestTemplate.render(pythonVersion=pythonVersion,framework=framework)

    # Generate the opinionated folder structure
    skaffoldDir = f'{generatedLocation}/{pythonVersion}/{frameworkName}'
    Path(skaffoldDir).mkdir(parents=True, exist_ok=True)

    # Generate k8s manifest for the given python version and framework
    skaffoldFile = f'{skaffoldDir}/{pythonVersion}-{framework}.yaml'
    with open(skaffoldFile, 'w') as f:
        f.write(output)

    updateProfiles(framework)


## Helper functions
#########
def getPythonVersion(version):
    """Given the format python-version then returns version"""
    list = version.split("-")
    return list[1]

def getFrameworkName(framework):
    """Given the format framework-version then returns framework"""
    list = framework.split("-")
    return list[0]

def getFrameworkVersion(framework):
    """Given the format framework-version then returns version otherwise None"""
    list = framework.split("-")
    if len(list) > 1:
        return list[1]
    return None

def isExcluded(version, framework, excludeFile):
    """Given the version and framework then it returns whether the tuple is excluded"""
    for value in excludeFile.get('exclude'):
        if (value.get('PYTHON_VERSION') == version and value.get('FRAMEWORK') == framework):
            return True
    return False

def runCommand(cmd):
    """Given the command to run it runs the command and print the output"""
    click.echo(click.style(f"Running {cmd}", fg='blue'))
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True, shell=True) as p:
        for line in p.stdout:
            click.echo(click.style(line.strip(), fg='yellow'))

    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, p.args)

def updateProfiles(framework):
    """Given the python and framework then update the generated skaffold profiles for that framework and version"""
    name = getFrameworkName(framework)
    version = getFrameworkVersion(framework)
    # Render the template
    output = profileTemplate.render(framework=framework, name=name, version=version)

    profilesFile = f'{generatedLocation}/profiles.tmp'
    with open(profilesFile, 'a') as f:
        f.write(output)

## Main
#########

cli.add_command(generate)
cli.add_command(build)
cli.add_command(test)

if __name__ == '__main__':
    cli()
