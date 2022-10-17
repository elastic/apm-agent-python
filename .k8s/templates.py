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


from pathlib import Path

import utils
from jinja2 import Template



with open(utils.Constants.SKAFFOLD_TEMPLATE) as file_:
    skaffoldTemplate = Template(file_.read())


def generateSkaffoldTemplate(default, git_username):
    """Given the python and framework then generate the k8s manifest and skaffold profile"""
    output = skaffoldTemplate.render(version=utils.getPythonVersion(default), git_user=git_username)
    with open(utils.Constants.GENERATED_SKAFFOLD, "w") as f:
        f.write(output)


class Default:
    def __init__(self, version, git_user):
        self.version = version
        self.git_user = git_user

        with open(utils.Constants.DEFAULT_TEMPLATE) as file_:
            self.defaultManifestTemplate = Template(file_.read())

    def generate(self):
        output = self.defaultManifestTemplate.render(
        name=self.version, version=utils.getPythonVersion(self.version), git_user=self.git_user
        )
        with open(utils.Constants.GENERATED_DEFAULT, "w") as f:
            f.write(output)


class Manifest:
    def __init__(self, python, framework, timeout, ttl, git_user):
        self.python = python
        self.framework = framework
        self.timeout = timeout
        self.ttl = ttl
        self.git_user = git_user

        with open(utils.Constants.MANIFEST_TEMPLATE) as file_:
            self.manifestTemplate = Template(file_.read())

    def generate(self):
        """Given the python and framework then generate the k8s manifest and skaffold profile"""
        pythonVersion = utils.getPythonVersion(self.python)
        frameworkName = utils.getFrameworkName(self.framework)

        # Render the template
        output = self.manifestTemplate.render(
            pythonVersion=pythonVersion,
            framework=self.framework,
            timeout=self.timeout,
            ttl=self.ttl,
            git_user=self.git_user,
        )

        # Generate the opinionated folder structure
        skaffoldDir = f"{utils.Constants.GENERATED}/{pythonVersion}/{frameworkName}"
        Path(skaffoldDir).mkdir(parents=True, exist_ok=True)

        # Generate k8s manifest for the given python version and framework
        skaffoldFile = f"{skaffoldDir}/{pythonVersion}-{self.framework}.yaml"
        with open(skaffoldFile, "w") as f:
            f.write(output)

        return skaffoldFile


class Profile:
    def __init__(self, python, framework):
        self.python = python
        self.framework = framework

        with open(utils.Constants.FRAMEWORK_TEMPLATE) as file_:
            self.frameworkTemplate = Template(file_.read())

    def generate(self):
        """Given the framework then update the generated skaffold profiles for that framework"""
        frameworkName = utils.getFrameworkName(self.framework)
        frameworkVersion = utils.getFrameworkVersion(self.framework)
        pythonVersion = utils.getPythonVersion(self.python)

        output = self.frameworkTemplate.render(
            framework=self.framework,
            frameworkName=frameworkName,
            frameworkVersion=frameworkVersion,
            python=self.python,
            pythonVersion=pythonVersion,
        )

        with open(utils.Constants.GENERATED_PROFILE, "a") as f:
            f.write(output)

        return utils.Constants.GENERATED_PROFILE


class VersionProfile:
    def __init__(self, version, default, git_user):
        self.version = version
        self.default = default
        self.git_user = git_user

        with open(utils.Constants.PYTHON_TEMPLATE) as file_:
            self.pythonTemplate = Template(file_.read())

    def generate(self):
        """Given the python then update the generated skaffold profiles for that version"""
        pythonVersion = utils.getPythonVersion(self.version)
        output = self.pythonTemplate.render(
            name=self.version, version=pythonVersion, default=self.default, git_user=self.git_user
        )

        with open(utils.Constants.GENERATED_PROFILE, "a") as f:
            f.write(output)

        return utils.Constants.GENERATED_PROFILE
