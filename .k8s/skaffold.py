from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import yaml
from jinja2 import Template
from pathlib import Path


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

# Parse command line arguments
parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument("-v", "--version", default=".ci/.jenkins_python.yml", help="YAML file with the list of versions.")
parser.add_argument("-f", "--framework", default=".ci/.jenkins_framework.yml", help="YAML file with the list of frameworks.")
parser.add_argument("-e", "--exclude", default=".ci/.jenkins_exclude.yml", help="YAML file with the list of version/framework that are excluded.")
args = vars(parser.parse_args())

with open('.k8s/templates/manifest.yaml.tmpl') as file_:
    manifestTemplate = Template(file_.read())

with open('.k8s/templates/profile.yaml.tmpl') as file_:
    profileTemplate = Template(file_.read())

# Read files
with open(args["version"], "r") as fp:
    versionFile = yaml.safe_load(fp)
with open(args["framework"], "r") as fp:
    frameworkFile = yaml.safe_load(fp)
with open(args["exclude"], "r") as fp:
    excludeFile = yaml.safe_load(fp)

def isExcluded(version, framework):
    for value in excludeFile.get('exclude'):
        if (value.get('PYTHON_VERSION') == version and value.get('FRAMEWORK') == framework):
            return True
    return False

def generateSkaffold(version, framework):
    print(" - generating skaffold for " + version + " and " + framework)
    pythonVersion = getPythonVersion(version)
    frameworkName = getFrameworkName(framework)

    # Render the template
    output = manifestTemplate.render(pythonVersion=pythonVersion,framework=framework)

    # Generate the opinionated folder structure
    skaffoldDir = f'.k8s/generated/k8s/{pythonVersion}/{frameworkName}'
    Path(skaffoldDir).mkdir(parents=True, exist_ok=True)

    # Generate k8s manifest for the given python version and framework
    skaffoldFile = f'{skaffoldDir}/{pythonVersion}-{framework}.yaml'
    with open(skaffoldFile, 'w') as f:
        f.write(output)

    updateProfiles(framework)

def updateProfiles(framework):
    """Given the python and framework then update the generated skaffold profiles for that framework and version"""

    name = getFrameworkName(framework)
    version = getFrameworkVersion(framework)
    # Render the template
    output = profileTemplate.render(framework=framework, name=name, version=version)

    profilesFile = f'.k8s/generated/profiles.yaml'
    with open(profilesFile, 'a') as f:
        f.write(output)

def main():
    print("Generating kubernetes configuration on the fly...")
    # Generate the skaffold files
    for version in versionFile.get('PYTHON_VERSION'):
        for framework in frameworkFile.get('FRAMEWORK'):
            if not isExcluded(version, framework):
                generateSkaffold(version, framework)
    print("Generating skaffold configuration on the fly...")
    filenames = ['.k8s/templates/skaffold.yaml.tmpl', '.k8s/generated/profiles.yaml']
    with open('skaffold.yml', 'w') as outfile:
        for fname in filenames:
            with open(fname) as infile:
                for line in infile:
                    outfile.write(line)

if __name__ == '__main__':
    main()
