#!/usr/bin/python
from pathlib import Path

import utils
from jinja2 import Template

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


def generateSkaffoldEntries(version, framework, ttl, git_username):
    """Given the python and framework then generate the k8s manifest and skaffold profile"""
    pythonVersion = utils.getPythonVersion(version)
    frameworkName = utils.getFrameworkName(framework)

    # Render the template
    output = manifestTemplate.render(pythonVersion=pythonVersion, framework=framework, ttl=ttl, git_user=git_username)

    # Generate the opinionated folder structure
    skaffoldDir = f"{utils.Constants.GENERATED}/{pythonVersion}/{frameworkName}"
    Path(skaffoldDir).mkdir(parents=True, exist_ok=True)

    # Generate k8s manifest for the given python version and framework
    skaffoldFile = f"{skaffoldDir}/{pythonVersion}-{framework}.yaml"
    with open(skaffoldFile, "w") as f:
        f.write(output)

    generateFrameworkProfiles(version, framework)


def generateSkaffoldTemplate(default, git_username):
    """Given the python and framework then generate the k8s manifest and skaffold profile"""
    output = skaffoldTemplate.render(version=utils.getPythonVersion(default), git_user=git_username)
    with open(utils.Constants.GENERATED_SKAFFOLD, "w") as f:
        f.write(output)


def generateDefaultManifest(version, git_username):
    """Given the python then generate the default manifest"""
    output = defaultManifestTemplate.render(
        name=version, version=utils.getPythonVersion(version), git_user=git_username
    )
    with open(utils.Constants.GENERATED_DEFAULT, "w") as f:
        f.write(output)


def generateVersionProfiles(version, default, git_username):
    """Given the python then update the generated skaffold profiles for that version"""
    pythonVersion = utils.getPythonVersion(version)
    # Render the template
    output = pythonTemplate.render(name=version, version=pythonVersion, default=default, git_user=git_username)
    appendProfile(output)


def generateFrameworkProfiles(python, framework):
    """Given the framework then update the generated skaffold profiles for that framework"""
    frameworkName = utils.getFrameworkName(framework)
    frameworkVersion = utils.getFrameworkVersion(framework)
    pythonVersion = utils.getPythonVersion(python)
    # Render the template
    output = frameworkTemplate.render(
        framework=framework,
        frameworkName=frameworkName,
        frameworkVersion=frameworkVersion,
        python=python,
        pythonVersion=pythonVersion,
    )
    appendProfile(output)


def appendProfile(output):
    with open(utils.Constants.GENERATED_PROFILE, "a") as f:
        f.write(output)
