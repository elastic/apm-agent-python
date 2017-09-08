#!groovy

def python_versions = ['python:2.7','python:3.3','python:3.4','python:3.5','python:3.6','pypy:2', 'pypy:3']
def frameworks = ['django-1.8', 'django-1.9', 'django-1.10', 'django-1.11', 'django-master', 'flask-0.10', 'flask-0.11', 'flask-0.12']
def exclude_jobs = ['python:2.7_django-master', 'python:3.3_django-1.9', 'python:3.3_django-1.10', 'python:3.3_django-1.11', 'python:3.3_django-master']
def test_jobs = [:]
def linters = ['isort', 'flake8']
def linter_jobs = [:]


properties([pipelineTriggers([githubPush()])])
node{
    withEnv(["HOME=/var/lib/jenkins",
             "PIP_CACHE=.cache/pip"
             ]) {
        stage('Checkout'){
            node('linux'){
                sh 'echo "do some SCM checkout..."'
                checkout scm
            }
        }
        
        stage('Lint'){
            linters.each {
                linter_jobs["${it}"] = {
                    node('linux'){
                        checkout scm
                        dir('src/github.com/elastic/apm-agent-python/'){
                            sh("./tests/scripts/docker/cleanup.sh")
                            sh("./tests/scripts/docker/${it}.sh")
                        }
                    }
                }
            }
            parallel linter_jobs
        }

        stage('Docs'){
            node('linux'){
                checkout scm
                dir('src/github.com/elastic/apm-agent-python/'){
                    sh("./tests/scripts/docker/docs.sh")
                }
            }
        } 
        
        stage("Test Run"){
            for (int i=0; i<python_versions.size(); i++){
                def py_ver = python_versions[i].toString()
                for (int j=0; j<frameworks.size(); j++){
                    def framework = frameworks[j].toString()
                    def job = "${py_ver}_${framework}".toString()
                    if(exclude_jobs.contains(job)){
                        continue 
                    }
                    test_jobs[job] = {
                        node('linux'){
                            checkout scm
                            try{ sh 'docker stop $(docker ps -q -a)' }catch(e){}
                            try{ sh 'docker rm -v $(docker ps -a -q)' }catch(e){}
                            dir('src/github.com/elastic/apm-agent-python/'){
                                sh("./tests/scripts/docker/cleanup.sh")
                                try{
                                    sh("./tests/scripts/docker/run_tests.sh ${py_ver} ${framework}")
                                }catch(e){
                                    if(!job.contains("django-master") && !job.equals("pypy:3_flask-0.11")){
                                        throw e
                                    }
                                }
                            }
                        }
                    }
                }
            }
            parallel test_jobs
        }
    }
}
