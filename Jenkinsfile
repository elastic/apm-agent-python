#!/usr/bin/env groovy
@Library('apm@current') _

import co.elastic.matrix.*
import groovy.transform.Field

/**
This is the parallel tasks generator,
it is need as field to store the results of the tests.
*/
@Field def pythonTasksGen

pipeline {
  agent { label 'linux && immutable' }
  environment {
    REPO = 'apm-agent-python'
    BASE_DIR = "src/github.com/elastic/${env.REPO}"
    PIPELINE_LOG_LEVEL='INFO'
    NOTIFY_TO = credentials('notify-to')
    JOB_GCS_BUCKET = credentials('gcs-bucket')
    CODECOV_SECRET = 'secret/apm-team/ci/apm-agent-python-codecov'
    GITHUB_CHECK_ITS_NAME = 'Integration Tests'
    ITS_PIPELINE = 'apm-integration-tests-selector-mbp/master'
  }
  options {
    timeout(time: 1, unit: 'HOURS')
    buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '20', daysToKeepStr: '30'))
    timestamps()
    ansiColor('xterm')
    disableResume()
    durabilityHint('PERFORMANCE_OPTIMIZED')
    rateLimitBuilds(throttle: [count: 60, durationName: 'hour', userBoost: true])
    quietPeriod(10)
  }
  triggers {
    issueCommentTrigger('(?i).*(?:jenkins\\W+)?run\\W+(?:the\\W+)?tests(?:\\W+please)?.*')
  }
  parameters {
    booleanParam(name: 'Run_As_Master_Branch', defaultValue: false, description: 'Allow to run any steps on a PR, some steps normally only run on master branch.')
  }
  stages {
    stage('Initializing'){
      options { skipDefaultCheckout() }
      environment {
        HOME = "${env.WORKSPACE}"
        PATH = "${env.PATH}:${env.WORKSPACE}/bin"
        ELASTIC_DOCS = "${env.WORKSPACE}/elastic/docs"
      }
      stages {
        /**
        Checkout the code and stash it, to use it on other stages.
        */
        stage('Checkout') {
          steps {
            deleteDir()
            gitCheckout(basedir: "${BASE_DIR}", githubNotifyFirstTimeContributor: true)
            stash allowEmpty: true, name: 'source', useDefaultExcludes: false
          }
        }
        stage('Sanity checks') {
          when {
            beforeAgent true
            anyOf {
              not { changeRequest() }
              expression { return params.Run_As_Master_Branch }
            }
          }
          steps {
            withGithubNotify(context: 'Sanity checks', tab: 'tests') {
              deleteDir()
              unstash 'source'
              script {
                docker.image('python:3.7-stretch').inside("-e PATH=${PATH}:${env.WORKSPACE}/bin"){
                  dir("${BASE_DIR}"){
                    // registry: '' will help to disable the docker login
                    preCommit(commit: "${GIT_BASE_COMMIT}", junit: true, registry: '')
                  }
                }
              }
            }
          }
        }
      }
    }
    /**
    Execute unit tests.
    */
    stage('Test') {
      options { skipDefaultCheckout() }
      steps {
        withGithubNotify(context: 'Test', tab: 'tests') {
          deleteDir()
          unstash "source"
          dir("${BASE_DIR}"){
            script {
              pythonTasksGen = new PythonParallelTaskGenerator(
                xKey: 'PYTHON_VERSION',
                yKey: 'FRAMEWORK',
                xFile: ".ci/.jenkins_python.yml",
                yFile: ".ci/.jenkins_framework.yml",
                exclusionFile: ".ci/.jenkins_exclude.yml",
                tag: "Python",
                name: "Python",
                steps: this
                )
              def mapPatallelTasks = pythonTasksGen.generateParallelTests()
              parallel(mapPatallelTasks)
            }
          }
        }
      }
    }
    stage('Building packages') {
      options { skipDefaultCheckout() }
      environment {
        HOME = "${env.WORKSPACE}"
        PATH = "${env.PATH}:${env.WORKSPACE}/.local/bin"
      }
      steps {
        withGithubNotify(context: 'Building packages') {
          deleteDir()
          unstash 'source'
          dir("${BASE_DIR}"){
            sh script: 'pip3 install --user cibuildwheel', label: "Installing cibuildwheel"
            sh script: 'mkdir wheelhouse', label: "creating wheelhouse"
            sh script: 'cibuildwheel --platform linux --output-dir wheelhouse; ls -l wheelhouse'
          }
          stash allowEmpty: true, name: 'packages', includes: "${BASE_DIR}/wheelhouse/*.whl,${BASE_DIR}/dist/*.tar.gz", useDefaultExcludes: false
        }
      }
    }
    stage('Integration Tests') {
      agent none
      when {
        beforeAgent true
        allOf {
          anyOf {
            environment name: 'GIT_BUILD_CAUSE', value: 'pr'
            expression { return !params.Run_As_Master_Branch }
          }
        }
      }
      steps {
        log(level: 'INFO', text: 'Launching Async ITs')
        build(job: env.ITS_PIPELINE, propagate: false, wait: false,
              parameters: [string(name: 'AGENT_INTEGRATION_TEST', value: 'Python'),
                           string(name: 'BUILD_OPTS', value: "--with-agent-python-flask --python-agent-package git+https://github.com/${env.CHANGE_FORK?.trim() ?: 'elastic' }/${env.REPO}.git@${env.GIT_BASE_COMMIT}"),
                           string(name: 'GITHUB_CHECK_NAME', value: env.GITHUB_CHECK_ITS_NAME),
                           string(name: 'GITHUB_CHECK_REPO', value: env.REPO),
                           string(name: 'GITHUB_CHECK_SHA1', value: env.GIT_BASE_COMMIT)])
        githubNotify(context: "${env.GITHUB_CHECK_ITS_NAME}", description: "${env.GITHUB_CHECK_ITS_NAME} ...", status: 'PENDING', targetUrl: "${env.JENKINS_URL}search/?q=${env.ITS_PIPELINE.replaceAll('/','+')}")
      }
    }
    stage('Release') {
      options { skipDefaultCheckout() }
      environment {
        HOME = "${env.WORKSPACE}"
        PATH = "${env.PATH}:${env.WORKSPACE}/.local/bin"
      }
      stages {
        stage('Notify') {
          steps {
              emailext subject: '[apm-agent-python] Release ready to be pushed',
                       to: 'victor.martinez@elastic.co',
                       body: "Please go to ${env.BUILD_URL}/input to approve or reject within 12 hours."
          }
        }
        stage('Release') {
          input {
            message 'Should we release a new version?'
            ok 'Yes, we should.'
            parameters {
              choice(
                choices: [
                  'https://upload.pypi.org/legacy/',
                  'https://test.pypi.org/legacy/'
                 ],
                 description: 'PyPI repository URL',
                 name: 'REPO_URL')
            }
          }
          steps {
            withGithubNotify(context: 'Release') {
              deleteDir()
              unstash 'source'
              unstash('packages')
            }
          }
        }
      }
    }
  }
  post {
    cleanup {
      script{
        if(pythonTasksGen?.results){
          writeJSON(file: 'results.json', json: toJSON(pythonTasksGen.results), pretty: 2)
          def mapResults = ["${params.agent_integration_test}": pythonTasksGen.results]
          def processor = new ResultsProcessor()
          processor.processResults(mapResults)
          archiveArtifacts allowEmptyArchive: true, artifacts: 'results.json,results.html', defaultExcludes: false
          catchError(buildResult: 'SUCCESS') {
            def datafile = readFile(file: "results.json")
            def json = getVaultSecret(secret: 'secret/apm-team/ci/apm-server-benchmark-cloud')
            sendDataToElasticsearch(es: json.data.url, data: datafile, restCall: '/jenkins-builds-test-results/_doc/')
          }
        }
      }
      notifyBuildResult()
    }
  }
}


/**
Parallel task generator for the integration tests.
*/
class PythonParallelTaskGenerator extends DefaultParallelTaskGenerator {

  public PythonParallelTaskGenerator(Map params){
    super(params)
  }

  /**
  build a map of closures to be used as parallel steps.
  Make 5 groups per column so it will spin 5 Nodes,
  this makes fewer Docker image Builds.
  */
  protected Map generateParallelSteps(column){
    def parallelStep = [:]
    def groups = [:]
    def index = 1
    column.each{ key, value ->
      def keyGrp = "${this.tag}-${value.x}-${index % 5}"
      if(groups[keyGrp] == null){
        groups[keyGrp] = [:]
        groups[keyGrp].key = value.x
        groups[keyGrp].values = []
      }
      groups[keyGrp].values.add(value.y)
      index++
    }
    groups.each{ key, value ->
      parallelStep[key] = generateStep(value.key, value.values)
    }
    return parallelStep
  }

  /**
  build a clousure that launch and agent and execute the corresponding test script,
  then store the results.
  */
  public Closure generateStep(x, yList){
    return {
      steps.node('linux && immutable'){
        yList.each{ y ->
          def label = "${tag}-${x}-${y}"
          try {
            steps.runScript(label: label, python: x, framework: y)
            saveResult(x, y, 1)
          } catch(e){
            saveResult(x, y, 0)
            steps.error("${label} tests failed : ${e.toString()}\n")
          } finally {
            steps.junit(allowEmptyResults: true,
              keepLongStdio: true,
              testResults: "**/python-agent-junit.xml,**/target/**/TEST-*.xml")
            steps.env.PYTHON_VERSION = "${x}"
            steps.env.WEBFRAMEWORK = "${y}"
            steps.codecov(repo: "${steps.env.REPO}",
              basedir: "${steps.env.BASE_DIR}",
              flags: "-e PYTHON_VERSION,WEBFRAMEWORK",
              secret: "${steps.env.CODECOV_SECRET}")
          }
        }
      }
    }
  }
}

def runScript(Map params = [:]){
  def label = params.label
  def python = params.python
  def framework = params.framework
  log(level: 'INFO', text: "${label}")
  env.HOME = "${env.WORKSPACE}"
  env.PATH = "${env.PATH}:${env.WORKSPACE}/bin"
  env.PIP_CACHE = "${env.WORKSPACE}/.cache"
  deleteDir()
  sh "mkdir ${env.PIP_CACHE}"
  unstash 'source'
  dir("${BASE_DIR}"){
    retry(2){
      sleep randomNumber(min:10, max: 30)
      sh("./tests/scripts/docker/run_tests.sh ${python} ${framework}")
    }
  }
}

def releasePackages(){
  def vault_secret = (env.REPO_URL == 'https://upload.pypi.org/legacy/') ? 'secret/apm-team/ci/apm-agent-python-pypi-prod' : 'secret/apm-team/ci/apm-agent-python-pypi-test'
  withSecretVault(secret: vault_secret,
                  user_var_name: 'TWINE_USER', pass_var_name: 'TWINE_PASSWORD'){
    sh(label: "Release packages", script: """
    set +x
    python -m pip install --user twine
    python setup.py sdist
    echo "Uploading to ${REPO_URL} with user \${TWINE_USER}"
    python -m twine upload --username "\${TWINE_USER}" --password "\${TWINE_PASSWORD}" --skip-existing --repository-url \${REPO_URL} dist/*.tar.gz
    python -m twine upload --username "\${TWINE_USER}" --password "\${TWINE_PASSWORD}" --skip-existing --repository-url \${REPO_URL} wheelhouse/*.whl
    """)
  }
}
