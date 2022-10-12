#!/usr/bin/python
import click
import subprocess

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

