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


import shutil
import uuid
from pathlib import Path

import click
import k8s
import templates
import utils
import yaml
from exceptions import ExistingFailedJobs


@click.command("generate", short_help="Generate the Skaffold context")
@click.option("--default", "-d", show_default=True, default="python-3.10", help="Default python version")
@click.option(
    "--dependencies",
    "-de",
    show_default=True,
    default=".ci/.jenkins_framework_dependencies.yml",
    help="YAML file with the dependencies for each framework",
)
@click.option(
    "--exclude",
    "-e",
    show_default=True,
    default=".ci/.jenkins_exclude.yml",
    help="YAML file with the list of version/framework tuples that are excluded",
)
@click.option("--force", is_flag=True, help="Whether to override the existing files")
@click.option(
    "--framework",
    "-f",
    show_default=True,
    default=".ci/.jenkins_framework.yml",
    help="YAML file with the list of frameworks",
)
@click.option("--timeout", show_default=True, default="600", help="K8s activeDeadlineSeconds")
@click.option("--ttl", "-t", show_default=True, default="100", help="K8s ttlSecondsAfterFinished")
@click.option(
    "--version", "-v", show_default=True, default=".ci/.jenkins_python.yml", help="YAML file with the list of versions"
)
def generate(default, dependencies, exclude, force, framework, timeout, ttl, version):
    """Generate the Skaffold files for the given python and frameworks."""
    # Read files
    with open(version, "r") as fp:
        versionFile = yaml.safe_load(fp)
    with open(framework, "r") as fp:
        frameworkFile = yaml.safe_load(fp)
    with open(exclude, "r") as fp:
        excludeFile = yaml.safe_load(fp)
    with open(dependencies, "r") as fp:
        dependenciesFile = yaml.safe_load(fp)

    # Generate the generated and build folders
    Path(utils.Constants.GENERATED).mkdir(parents=True, exist_ok=force)
    Path(utils.Constants.BUILD).mkdir(parents=True, exist_ok=force)

    click.echo(click.style("Generating kubernetes configuration on the fly...", fg="yellow"))

    # To help with identifying the k8s resources
    git_username = utils.git_username()

    # Generate profiles for the given python versions
    for ver in versionFile.get("PYTHON_VERSION"):
        versionProfile = templates.VersionProfile(ver, default, git_username)
        versionProfile.generate()

    # Generate profiles for the given python and framewok versions
    for ver in versionFile.get("PYTHON_VERSION"):
        for fra in frameworkFile.get("FRAMEWORK"):
            if not utils.isExcluded(ver, fra, excludeFile):
                # IMPORTANT: to be implemented in the future but for now
                # as long as we don't support dependencies within the same pod
                # let's skip those frameworks with dependencies
                if not utils.isFrameworkWithDependencies(fra, dependenciesFile):
                    manifest = templates.Manifest(ver, fra, timeout, ttl, git_username)
                    manifest.generate()

                    profile = templates.SkaffoldProfile(ver, fra)
                    profile.generate()

    click.echo(click.style("Generating skaffold configuration on the fly...", fg="yellow"))

    # Generate skaffold with the default python version
    # skaffold requires a default manifest ... this is the workaround for now.
    skaffold = templates.Skaffold(default, git_username)
    skaffold.generate()

    # Aggregate all the skaffold files and converge (order matters!)
    filenames = [utils.Constants.GENERATED_SKAFFOLD, utils.Constants.GENERATED_PROFILE]
    with open("skaffold.yaml", "w") as outfile:
        for fname in filenames:
            with open(fname) as infile:
                for line in infile:
                    outfile.write(line)

    click.echo(click.style("Copying dockerignore file...", fg="yellow"))
    # avoid exposing anything unrelated to the source code.
    shutil.copyfile(".k8s/.dockerignore", ".dockerignore")

    click.echo(click.style("Copying default yaml file...", fg="yellow"))
    # skaffold requires a default manifest ... this is the workaround for now.
    default = templates.Default(default, git_username)
    default.generate()


@click.command("build", short_help="Build the docker images")
@click.option("--version", "-v", multiple=True, help="Python version to be built")
@click.option("--repo", "-r", show_default=True, default="docker.elastic.co/beats-dev", help="Docker repository")
@click.option("--extra", "-x", help="Extra arguments for the skaffold tool.")
def build(version, repo, extra):
    """Build docker images that contain your workspace and publish them to the given Docker repository."""
    # Enable the skaffold profiles matching the given version, if any
    profilesFlag = "-p " + ",".join(version) if version else ""
    repositoryFlag = f"--default-repo={repo}" if repo else ""
    extraFlag = f"{extra}" if extra else ""
    command = (
        f"skaffold build {repositoryFlag} --file-output={utils.Constants.GENERATED_TAGS} {profilesFlag} {extraFlag}"
    )
    utils.runCommand(command)


@click.command("test", short_help="Test support matrix")
@click.option("--framework", "-f", multiple=True, help="Framework to be tested.")
@click.option("--version", "-v", multiple=True, help="Python version to be tested.")
@click.option("--extra", "-x", help="Extra arguments for the skaffold tool.")
@click.option("--namespace", "-n", show_default=True, default="default", help="Run the in the specified namespace")
def test(framework, version, extra, namespace):
    """Run the test support matrix for the default version and frameworks or filtered by them."""
    Path(utils.Constants.BUILD).mkdir(parents=True, exist_ok=True)
    filter = uuid.uuid4()
    deploy(framework, version, extra, namespace, filter)
    results = k8s.results(framework, version, namespace, utils.git_username(), filter)
    if results is not None and len(results.get("failed")) > 0:
        raise ExistingFailedJobs(results.get("failed"))


@click.command("results", short_help="Query results")
@click.option("--framework", "-f", multiple=True, help="Framework to be tested.")
@click.option("--version", "-v", multiple=True, help="Python version to be tested.")
@click.option("--namespace", "-n", show_default=True, default="default", help="Run the in the specified namespace")
def results(framework, version, namespace):
    """Query the results for the given version and frameworks or filtered by them."""
    Path(utils.Constants.BUILD).mkdir(parents=True, exist_ok=True)
    results = k8s.results(framework, version, namespace, utils.git_username(), None)
    if results is not None and len(results.get("failed")) > 0:
        raise ExistingFailedJobs(results.get("failed"))


def deploy(framework, version, extra, namespace, filter):
    """Given the python and framework then run the skaffold deployment"""
    profilesFlag = getProfileVersionFramework(framework, version)
    extraFlag = f"{extra}" if extra else ""
    filterFlag = f"--label=filter={filter}" if filter else ""
    defaultCommand = f"skaffold deploy --build-artifacts={utils.Constants.GENERATED_TAGS}"
    command = f"{defaultCommand} -n {namespace} {profilesFlag} {extraFlag} {filterFlag}"
    utils.runCommand(command)


def getProfileVersionFramework(framework, version):
    if framework and version:
        framework_versions = []
        for v in version:
            for f in framework:
                framework_versions.append(f"{v}-{f}")
        return "-p " + ",".join(framework_versions) if (framework_versions) else ""
    else:
        return "-p " + ",".join(framework + version) if (framework or version) else ""
