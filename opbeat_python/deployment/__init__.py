

from opbeat_python.utils.deployment import get_versions_from_installed, get_version_from_distributions, get_repository_info,get_installed_distributions

# import opbeat_python.contrib.django.models
# from opbeat_python.contrib.django.models import get_installed_apps

# print get_versions(get_installed_apps())

# from opbeat_python.utils import get_versions, get_repository_info
from opbeat_python.conf import defaults

def send_deployment_info(client):
	versions = get_versions_from_installed(client.include_paths)
	dist_versions = get_version_from_distributions(get_installed_distributions())
	versions.update(dist_versions)

	rep_info = get_repository_info()

	if rep_info:
	  versions['_repository'] = {'module':client.name, 'vcs':rep_info}

	print versions

	urls = [server+defaults.DEPLOYMENT_API_PATH for server in client.servers]


