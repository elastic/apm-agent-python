#!/usr/bin/python
import click
from jinja2 import Template
import utils
import k8s
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


def generateSkaffoldEntries(version, framework):
    """Given the python and framework then generate the k8s manifest and skaffold profile"""
    # print(" - generating skaffold for " + version + " and " + framework)
    pythonVersion = utils.getPythonVersion(version)
    frameworkName = utils.getFrameworkName(framework)

    # Render the template
    output = manifestTemplate.render(pythonVersion=pythonVersion,framework=framework)

    # Generate the opinionated folder structure
    skaffoldDir = f'{utils.Constants.GENERATED}/{pythonVersion}/{frameworkName}'
    Path(skaffoldDir).mkdir(parents=True, exist_ok=True)

    # Generate k8s manifest for the given python version and framework
    skaffoldFile = f'{skaffoldDir}/{pythonVersion}-{framework}.yaml'
    with open(skaffoldFile, 'w') as f:
        f.write(output)

    generateFrameworkProfiles(framework)


def generateDefaultManifest(version):
    """Given the python then generate the default manifest"""
    output = defaultManifestTemplate.render(name=version, version=utils.getPythonVersion(version))
    with open(utils.Constants.GENERATED_DEFAULT, 'w') as f:
        f.write(output)


def generateVersionProfiles(version):
    """Given the python then update the generated skaffold profiles for that version"""
    pythonVersion = utils.getPythonVersion(version)
    # Render the template
    output = pythonTemplate.render(name=version, version=pythonVersion)
    appendProfile(output)


def generateFrameworkProfiles(framework):
    """Given the framework then update the generated skaffold profiles for that framework"""
    name = utils.getFrameworkName(framework)
    version = utils.getFrameworkVersion(framework)
    # Render the template
    output = frameworkTemplate.render(framework=framework, name=name, version=version)
    appendProfile(output)


def appendProfile(output):
    with open(utils.Constants.GENERATED_PROFILE, 'a') as f:
        f.write(output)
