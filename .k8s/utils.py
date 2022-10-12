#!/usr/bin/python
import click
import subprocess
from typing import Final

class Constants:
    """All constants"""

    # pylint: disable=R0903
    TEMPLATES: Final[str] = ".k8s/templates"
    BUILD: Final[str] = "build"
    GENERATED: Final[str] = ".k8s/generated"
    DEFAULT_TEMPLATE: Final[str] = f"{TEMPLATES}/default.yaml.tmpl"
    MANIFEST_TEMPLATE: Final[str] = f"{TEMPLATES}/manifest.yaml.tmpl"
    FRAMEWORK_TEMPLATE: Final[str] = f"{TEMPLATES}/framework.profile.yaml.tmpl"
    PYTHON_TEMPLATE: Final[str] = f"{TEMPLATES}/python.profile.yaml.tmpl"
    SKAFFOLD_TEMPLATE: Final[str] = f"{TEMPLATES}/skaffold.yaml.tmpl"
    GENERATED_DEFAULT: Final[str] = f'{GENERATED}/default.yaml'
    GENERATED_SKAFFOLD: Final[str] = f'{GENERATED}/skaffold.yaml.tmp'
    GENERATED_PROFILE: Final[str] = f'{GENERATED}/profiles.tmp'
    GENERATED_TAGS: Final[str] = f'{GENERATED}/tags.json'


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
