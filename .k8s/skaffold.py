from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import yaml
from jinja2 import Template
from pathlib import Path

# Parse command line arguments
parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument("-v", "--version", default=".ci/.jenkins_python.yml", help="YAML file with the list of versions.")
parser.add_argument("-f", "--framework", default=".ci/.jenkins_framework.yml", help="YAML file with the list of frameworks.")
parser.add_argument("-e", "--exclude", default=".ci/.jenkins_exclude.yml", help="YAML file with the list of version/framework that are excluded.")
args = vars(parser.parse_args())

with open('.k8s/manifest.yaml.tmpl') as file_:
    template = Template(file_.read())

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

def getPythonVersion(version):
    # Given the format python-3.9 or python-3.6
    # Then return 3.9 or 3.6
    list = version.split("-")
    return list[1]

def getFrameworkName(framework):
    # Given the format framework-version
    # Then return framework
    list = framework.split("-")
    return list[0]

def getFrameworkVersion(framework):
    # Given the format framework-version
    # Then return version
    list = framework.split("-")
    return list[1]

def generateSkaffold(version, framework):
    print(" - generating skaffold for " + version + " and " + framework)
    pythonVersion = getPythonVersion(version)
    frameworkName = getFrameworkName(framework)
    output = template.render(pythonVersion=pythonVersion,framework=framework)
    skaffoldDir = f'.k8s/generated/k8s/{pythonVersion}/{frameworkName}'
    Path(skaffoldDir).mkdir(parents=True, exist_ok=True)
    skaffoldFile = f'{skaffoldDir}/{pythonVersion}-{framework}.yaml'
    with open(skaffoldFile, 'w') as f:
        f.write(output)

def updateSkaffold(version, framework):


def main():
     # Generate the skaffold files
    for version in versionFile.get('PYTHON_VERSION'):
        for framework in frameworkFile.get('FRAMEWORK'):
            if not isExcluded(version, framework):
                generateSkaffold(version, framework)

if __name__ == '__main__':
    main()
