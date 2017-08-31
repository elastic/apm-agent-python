#!groovy

def python_versions = ['2.7','3.3','3.4','3.5','3.6','pypy','latest']
def frameworks = ['django-1.8', 'django-1.9', 'django-1.10', 'django-1.11', 'django-master', 'flask-0.10', 'flask-0.11', 'flask-0.12']
def exclude_jobs = ['python-2.7_django-master', 'python-3.3_django-1.9', 'python-3.3_django-1.10', 'python-3.3_django-1.11', 'python-3.3_django-master']
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
            def label="build_no=${env.BUILD_ID}"
            def pip_cache = "${env.WORKSPACE}/${env.PIP_CACHE}"
            linters.each {
                linter_jobs["${it}"] = {
                    node('linux'){
                        try{
                            checkout scm
                            sh("./tests/scripts/docker/${it}.sh ${label} ${pip_cache}")
                        }finally{
                            sh("./tests/scripts/docker/remove.sh ${label}")
                        }
                    }
                }
            }
            parallel linter_jobs
        }
        
        stage("Test Run"){
            python_versions.each{ py_ver -> 
                frameworks.each{ framework -> 
                    def job = "python-${py_ver}_${framework}".toString()
                    if(exclude_jobs.contains(job)){
                        return
                    }
                    test_jobs[job] = {
                        node('linux'){
                            checkout scm
                            try{
                                sh("./tests/scripts/docker/run_tests.sh ${py_ver} ${framework}")
                            }catch(e){
                                if(!job.contains("python-latest") && !job.contains("django-master")){
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
