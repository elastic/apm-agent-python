#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import subprocess
from typing import Final

import click


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
    GENERATED_DEFAULT: Final[str] = f"{GENERATED}/default.yaml"
    GENERATED_SKAFFOLD: Final[str] = f"{GENERATED}/skaffold.yaml.tmp"
    GENERATED_PROFILE: Final[str] = f"{GENERATED}/profiles.tmp"
    GENERATED_TAGS: Final[str] = f"{GENERATED}/tags.json"


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
    for value in excludeFile.get("exclude"):
        if value.get("PYTHON_VERSION") == version and value.get("FRAMEWORK") == framework:
            return True
    return False


def isFrameworkWithDependencies(framework, dependenciesFile):
    """Given the framework and the list of dependencies then it returns whether it has some dependencies"""
    return len(getFrameworkDependencies(framework, dependenciesFile)) > 0


def getFrameworkDependencies(framework, dependenciesFile):
    """Given the framework and the list of dependencies then it returns its dependencies"""
    for value in dependenciesFile.get("dependencies"):
        if value.get("FRAMEWORK") == framework:
            return value.get("DEPENDENCIES")
    return []


def git_username():
    res = subprocess.run(["git", "config", "user.name"], stdout=subprocess.PIPE)
    return "".join(e for e in res.stdout.strip().decode() if e.isalnum()).lower()


def runCommand(cmd):
    """Given the command to run it runs the command and print the output"""
    click.echo(click.style(f"Running {cmd}", fg="blue"))
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True, shell=True) as p:
        for line in p.stdout:
            click.echo(click.style(line.strip(), fg="yellow"))

    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, p.args)
