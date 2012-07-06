# import sys
# import pkg_resources
# import os
# from distutils.sysconfig import get_python_lib

# # We store a cache of module_name->version string to avoid
# # continuous imports and lookups of modules
# _VERSION_CACHE = {}

# def get_git_repository_info():
#     cmd = ['git', 'log','-n','1','--pretty=format:"%H"']
#     git_commit_hash = exec_and_get_stdout(cmd)
    
#     if git_commit_hash:
#         git_commit_hash = git_commit_hash.strip('"')
#     else:
#         return None

#     cmd = ['git','name-rev', '--name-only', 'HEAD']
#     local_branch = exec_and_get_stdout(cmd)
    
#     cmd = ['git','config', 'branch.%s.remote' % local_branch]
#     remote_tracking = exec_and_get_stdout(cmd)

#     cmd = ['git','config', 'remote.%s.url' % remote_tracking]
#     remote_url = exec_and_get_stdout(cmd)

#     return {
#         'branch':local_branch,
#         'repository':remote_url,
#         'commit':git_commit_hash
#     }

# def get_repository_info():
#     try:
#         return get_git_repository_info()
#     except:
#         return None
