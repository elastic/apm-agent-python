import codecs
import json
import os
import shutil
import subprocess
import sys

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen

BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
WORKTREE = 'benchmarking_worktree'

def get_commit_list(commit_range):
    commits = subprocess.check_output(['git', 'log', "--pretty=%h", commit_range]).decode('utf8')
    commits = commits.split('\n')[:-1]
    commits.reverse()
    return commits


def run_benchmark(commit_hash):
    # clean up from former runs
    if os.path.exists('.benchmarks'):
        shutil.rmtree('.benchmarks')
    if os.path.exists(os.path.join('tests', 'ci_bench')):
        shutil.rmtree(os.path.join('tests', 'ci_bench'))
    subprocess.check_output(['git', 'checkout', 'elasticapm/base.py'])
    subprocess.check_output(['git', 'checkout', commit_hash])
    # copy newest benchmarks into work tree
    shutil.copytree(
        os.path.join(BASE_PATH, 'tests', 'instrumentation', 'benchmarks'),
        os.path.join('tests', 'ci_bench')
    )
    # set the timer thread to deamon, this fixes an issue with the timer thread
    # not exiting in old commits
    subprocess.check_output("sed -i '' -e 's/self\._send_timer\.start/self\._send_timer\.daemon=True; self\._send_timer\.start/g' elasticapm/base.py", shell=True)
    test_cmd = ['py.test', '-v', '-v', '--ignore=tests/asyncio', '-k', 'ci_bench',  '--benchmark-autosave', '--benchmark-max-time=10', '--benchmark-warmup=on', '--benchmark-warmup-iterations=10']
    print(' '.join(test_cmd))
    subprocess.check_output(
        test_cmd,
        stderr=subprocess.STDOUT,
    )
    shutil.rmtree(os.path.join('tests', 'ci_bench'))
    subprocess.check_output(['git', 'checkout', 'elasticapm/base.py'])
    f = subprocess.check_output(['find', '.benchmarks', '-name', '*%s*' % commit_hash]).decode('utf8').strip()
    return f


def upload(json_file, es_host):
    if not os.path.exists(json_file):
        sys.stderr.write('%s not found' % json_file)
        sys.exit(1)
    json_data = json.load(codecs.open(json_file, encoding='utf8'))
    url = es_host + '/agent_benchmarks/_doc/'
    for benchmark in json_data['benchmarks']:
        benchmark['machine_info'] = json_data['machine_info']
        benchmark['commit_info'] = json_data['commit_info']
        benchmark['@timestamp'] = json_data['commit_info']['author_time']
        req = Request(url, json.dumps(benchmark).encode('utf8'), {'Content-Type': 'application/json'})
        f = urlopen(req)
        response = f.read()
        f.close()


if __name__ == '__main__':
    base_branch, commit_range, es_host = sys.argv[1:]
    os.chdir(BASE_PATH)
    if not os.path.exists(WORKTREE):
        subprocess.check_output(['git', 'worktree', 'add', WORKTREE])
    os.chdir(WORKTREE)
    subprocess.check_output(['git', 'checkout', 'elasticapm/base.py'])
    subprocess.check_output(['git', 'checkout', base_branch])
    commits = get_commit_list(commit_range)
    for commit in commits:
        json_file = run_benchmark(commit)
        upload(json_file, es_host)
