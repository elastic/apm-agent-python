import sys
import pkg_resources
import os
from distutils.sysconfig import get_python_lib

# We store a cache of module_name->version string to avoid
# continuous imports and lookups of modules
_VERSION_CACHE = {}


def get_installed_distributions(local_only=True, skip=('setuptools', 'pip', 'python')):
    """
    Return a list of installed Distribution objects.

    If ``local_only`` is True (default), only return installations
    local to the current virtualenv, if in a virtualenv.

    ``skip`` argument is an iterable of lower-case project names to
    ignore; defaults to ('setuptools', 'pip', 'python'). [FIXME also
    skip virtualenv?]

    """
    if local_only:
        local_test = dist_is_local
    else:
        local_test = lambda d: True
    return [d for d in pkg_resources.working_set]# if local_test(d) and d.key not in skip]


def get_versions_from_installed(module_list=None):
    if not module_list:
        return {}

    ext_module_list = set()
    for m in module_list:
        parts = m.split('.')
        ext_module_list.update('.'.join(parts[:idx]) for idx in xrange(1, len(parts) + 1))

    versions = {}
    for module_name in ext_module_list:
        if module_name not in _VERSION_CACHE:
            try:
                __import__(module_name)
            except ImportError:
                continue
            app = sys.modules[module_name]
            if hasattr(app, 'get_version'):
                get_version = app.get_version
                if callable(get_version):
                    version = get_version()
                else:
                    version = get_version
            elif hasattr(app, 'VERSION'):
                version = app.VERSION
            elif hasattr(app, '__version__'):
                version = app.__version__
            
            # pull version from pkg_resources if distro exists
            try:
                d = pkg_resources.get_distribution(module_name)
                version = d.version
                location = d.location
                # location = os.path.join(os.path.normcase(os.path.abspath(d.location)),module_name)
                comments = []
                from pip.vcs import vcs, get_src_requirement
                print d.key, location, vcs.get_backend_name(location)
                            
            except pkg_resources.DistributionNotFound:
                version = None
        
            if isinstance(version, (list, tuple)):
                version = '.'.join(str(o) for o in version)
            _VERSION_CACHE[module_name] = version
        else:
            version = _VERSION_CACHE[module_name]
        if version is None:
            continue
        versions[module_name] = version
    return versions

def get_version_from_distributions(distributions):
    return {}
    # from pip.vcs import vcs, get_src_requirement
    # print d.key, location, vcs.get_backend_name(location)


def normalize_path(path):
    """
    Convert a path to its canonical, case-normalized, absolute version.

    """
    return os.path.normcase(os.path.realpath(path))

def is_local(path):
    """
    Return True if path is within sys.prefix, if we're running in a virtualenv.

    If we're not in a virtualenv, all paths are considered "local."

    """
    if not running_under_virtualenv():
        return True
    return normalize_path(path).startswith(normalize_path(sys.prefix))


def dist_is_local(dist):
    """
    Return True if given Distribution object is installed locally
    (i.e. within current virtualenv).

    Always True if we're not in a virtualenv.

    """
    return is_local(dist_location(dist))


def dist_in_usersite(dist):
    """
    Return True if given Distribution is installed in user site.
    """
    if user_site:
        return normalize_path(dist_location(dist)).startswith(normalize_path(user_site))
    else:
        return False

def egg_link_path(dist):
    """
    Return the path where we'd expect to find a .egg-link file for
    this distribution. (There doesn't seem to be any metadata in the
    Distribution object for a develop egg that points back to its
    .egg-link and easy-install.pth files).

    This won't find a globally-installed develop egg if we're in a
    virtualenv.

    """
    return os.path.join(site_packages, dist.project_name) + '.egg-link'


def dist_location(dist):
    """
    Get the site-packages location of this distribution. Generally
    this is dist.location, except in the case of develop-installed
    packages, where dist.location is the source code location, and we
    want to know where the egg-link file is.

    """
    egg_link = egg_link_path(dist)
    if os.path.exists(egg_link):
        return egg_link
    return dist.location

"""Locations where we look for configs, install stuff, etc"""

import sys
import site
import os
import tempfile
from pip.backwardcompat import get_python_lib


def running_under_virtualenv():
    """
    Return True if we're running inside a virtualenv, False otherwise.

    """
    return hasattr(sys, 'real_prefix')

def virtualenv_no_global():
    """
    Return True if in a venv and no system site packages.
    """
    #this mirrors the logic in virtualenv.py for locating the no-global-site-packages.txt file
    site_mod_dir = os.path.dirname(os.path.abspath(site.__file__))
    no_global_file = os.path.join(site_mod_dir,'no-global-site-packages.txt')
    if running_under_virtualenv() and os.path.isfile(no_global_file):
        return True

# FIXME doesn't account for venv linked to global site-packages

site_packages = get_python_lib()


def find_command(cmd, paths=None, pathext=None):
    """Searches the PATH for the given command and returns its path"""
    if paths is None:
        paths = os.environ.get('PATH', '').split(os.pathsep)
    if isinstance(paths, string_types):
        paths = [paths]
    # check if there are funny path extensions for executables, e.g. Windows
    if pathext is None:
        pathext = get_pathext()
    pathext = [ext for ext in pathext.lower().split(os.pathsep)]
    # don't use extensions if the command ends with one of them
    if os.path.splitext(cmd)[1].lower() in pathext:
        pathext = ['']
    # check if we find the command on PATH
    for path in paths:
        # try without extension first
        cmd_path = os.path.join(path, cmd)
        for ext in pathext:
            # then including the extension
            cmd_path_ext = cmd_path + ext
            if os.path.isfile(cmd_path_ext):
                return cmd_path_ext
        if os.path.isfile(cmd_path):
            return cmd_path
    raise BadCommand('Cannot find command %r' % cmd)


def exec_and_get_stdout(cmd):
    try:
        import subprocess
        p = subprocess.Popen(cmd,stdout=subprocess.PIPE)
        (stdoutdata, stderrdata) = p.communicate()
        return stdoutdata.strip()
    except Exception, ex:
        print ex
        return None


def get_git_repository_info():
    cmd = ['git', 'log','-n','1','--pretty=format:"%H"']
    git_commit_hash = exec_and_get_stdout(cmd)
    
    if git_commit_hash:
        git_commit_hash = git_commit_hash.strip('"')
    else:
        return None

    cmd = ['git','name-rev', '--name-only', 'HEAD']
    local_branch = exec_and_get_stdout(cmd)
    
    cmd = ['git','config', 'branch.%s.remote' % local_branch]
    remote_tracking = exec_and_get_stdout(cmd)

    cmd = ['git','config', 'remote.%s.url' % remote_tracking]
    remote_url = exec_and_get_stdout(cmd)

    return {
        'branch':local_branch,
        'repository':remote_url,
        'commit':git_commit_hash
    }

def get_repository_info():
    try:
        return get_git_repository_info()
    except:
        return None
