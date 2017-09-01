#!groovy

def python_versions = ['python:2.7','python:3.3','python:3.4','python:3.5','python:3.6','pypy:2', 'pypy:3']
def frameworks = ['django-1.8', 'django-1.9', 'django-1.10', 'django-1.11', 'django-master', 'flask-0.10', 'flask-0.11', 'flask-0.12']
def exclude_jobs = ['python:2.7_django-master', 'python:3.3_django-1.9', 'python:3.3_django-1.10', 'python:3.3_django-1.11', 'python:3.3_django-master']
def test_jobs = [:]
def linters = ['isort', 'flake8', 'docs']
def linter_jobs = [:]

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
            def pip_cache = "${env.WORKSPACE}/${env.PIP_CACHE}"
            linters.each {
                linter_jobs["${it}"] = {
                    node('linux'){
                        checkout scm
                        sh("./tests/scripts/docker/${it}.sh ${pip_cache}")
                    }
                }
            }
            parallel linter_jobs
        }
        
        stage("Test Run"){
            def pip_cache = "${env.WORKSPACE}/${env.PIP_CACHE}"
            python_versions.each{ py_ver -> 
                frameworks.each{ framework -> 
                    def job = "${py_ver}_${framework}".toString()
                    if(exclude_jobs.contains(job)){
                        return
                    }
                    test_jobs[job] = {
                        node('linux'){
                            checkout scm
                            try{
                                sh("./tests/scripts/docker/run_tests.sh ${py_ver} ${framework} ${pip_cache}")
                            }catch(e){
                                if(!job.contains("django-master") && !job.equals("pypy:3_flask-0.11")){
                                    throw e
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
