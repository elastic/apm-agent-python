#!/usr/bin/env groovy
import groovy.transform.Field

@Field def results = [:]

pipeline {
  agent none
  environment {
    BASE_DIR="src/github.com/elastic/apm-agent-python"
  }
  options {
    timeout(time: 1, unit: 'HOURS') 
    buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '20', daysToKeepStr: '30'))
    timestamps()
    ansiColor('xterm')
    disableResume()
    durabilityHint('PERFORMANCE_OPTIMIZED')
  }
  parameters {
    booleanParam(name: 'Run_As_Master_Branch', defaultValue: false, description: 'Allow to run any steps on a PR, some steps normally only run on master branch.')
    booleanParam(name: 'doc_ci', defaultValue: true, description: 'Enable build docs.')
  }
  stages {
    stage('Initializing'){
      agent { label 'docker && linux && immutable' }
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
            gitCheckout(basedir: "${BASE_DIR}")
            stash allowEmpty: true, name: 'source', useDefaultExcludes: false
            dir("${BASE_DIR}"){
              sh "git log origin/${env.CHANGE_TARGET}...${env.GIT_SHA}"
            }
          }
        }
        /**
         Build the project from code..
        */
        stage('Build') {
          steps {
            deleteDir()
            unstash 'source'
            dir("${BASE_DIR}"){
              sh """
              ./tests/scripts/docker/cleanup.sh
              ./tests/scripts/docker/isort.sh
              """
              sh """
              ./tests/scripts/docker/cleanup.sh
              ./tests/scripts/docker/black.sh
              """
            }
          }
        }
      }
    }
    /**
     Execute unit tests.
    */
    stage('Test') {
      agent { label 'docker && linux && immutable' }
      options { skipDefaultCheckout() }
      environment {
        HOME = "${env.WORKSPACE}"
        PATH = "${env.PATH}:${env.WORKSPACE}/bin"
        ELASTIC_DOCS = "${env.WORKSPACE}/elastic/docs"
      }
      steps {
        deleteDir()
        unstash 'source'
        script {
          def parallelStages = [:]
          //.findAll{ it.startsWith('pypy') }
          getPythonVersions().each{ py ->
            def matrix = buildMatrix(py)
            parallelStages[py] = launchInParallel(py, matrix)
          }
          parallel(parallelStages)
          writeJSON(file: 'results.json', data: results)
          archive('results.json')
        }
      }
      post { 
        always { 
          junit(allowEmptyResults: true, 
            keepLongStdio: true, 
            testResults: "${BASE_DIR}/**/python-agent-junit.xml,${BASE_DIR}/target/**/TEST-*.xml")
          //codecov(repo: 'apm-agent-python', basedir: "${BASE_DIR}", label: "${PYTHON_VERSION},${WEBFRAMEWORK}")
        }
      }
    }
    /**
      Build the documentation.
    */
    stage('Documentation') {
      agent { label 'docker && linux && immutable' }
      options { skipDefaultCheckout() }
      environment {
        HOME = "${env.WORKSPACE}"
        PATH = "${env.PATH}:${env.WORKSPACE}/bin"
        ELASTIC_DOCS = "${env.WORKSPACE}/elastic/docs"
      }
      when {
        beforeAgent true
        allOf {
          anyOf {
            not {
              changeRequest()
            }
            branch 'master'
            branch "\\d+\\.\\d+"
            branch "v\\d?"
            tag "v\\d+\\.\\d+\\.\\d+*"
            environment name: 'Run_As_Master_Branch', value: 'true'
          }
          environment name: 'doc_ci', value: 'true'
        }
      }
      steps {
        deleteDir()
        unstash 'source'
        checkoutElasticDocsTools(basedir: "${ELASTIC_DOCS}")
        dir("${BASE_DIR}"){
          sh './scripts/jenkins/docs.sh'
        }
      }
      post{
        success {
          tar(file: "doc-files.tgz", archive: true, dir: "html", pathPrefix: "${BASE_DIR}/docs")
        }
      }
    }
  }
  post { 
    success {
      echoColor(text: '[SUCCESS]', colorfg: 'green', colorbg: 'default')
    }
    aborted {
      echoColor(text: '[ABORTED]', colorfg: 'magenta', colorbg: 'default')
    }
    failure { 
      echoColor(text: '[FAILURE]', colorfg: 'red', colorbg: 'default')
      //step([$class: 'Mailer', notifyEveryUnstableBuild: true, recipients: "${NOTIFY_TO}", sendToIndividuals: false])
    }
    unstable { 
      echoColor(text: '[UNSTABLE]', colorfg: 'yellow', colorbg: 'default')
    }
  }
}

def launchInParallel(stageName, matrix){
  def testOdd = [:]
  def testEven = [:]
  matrix.each{ key, value, i ->
    def body = {
      env.PIP_CACHE = "${WORKSPACE}/.pip"
      deleteDir()
      sh "mkdir ${PIP_CACHE}"
      unstash 'source'
      dir("${BASE_DIR}"){
        def ret = sh(returnStatus: true, script: "./tests/scripts/docker/run_tests.sh ${value.python} ${value.framework}")
        if(results[value.python] == null){
          results[value.python] = [:]
        }
        results[value.python][value.framework] = ret
      }
      junit(allowEmptyResults: true, 
        keepLongStdio: true, 
        testResults: "${BASE_DIR}/**/python-agent-junit.xml,${BASE_DIR}/target/**/TEST-*.xml")
    }
    if(i%2 == 0){
      testOdd[key] = body
    } else {
      testEven[key] = body
    }
  }
  return {
    node('docker && linux && immutable'){
      stage("${stageName}-01"){
        testOdd.each{ key, value ->
          value()
        }
      }
    }
    node('docker && linux && immutable'){
      stage("${stageName}-02"){
        testEven.each{ key, value ->
          value()
        }
      }
    }
  }
}

def getPythonVersions(){
  return readYaml(file: "${BASE_DIR}/tests/.jenkins_python.yml")['PYTHON_VERSION']
}

def buildMatrix(py){
  def frameworks = readYaml(file: "${BASE_DIR}/tests/.jenkins_framework.yml")['FRAMEWORK']
  def excludes = readYaml(file: "${BASE_DIR}/tests/.jenkins_exclude.yml")['exclude'].collect{ "${it.PYTHON_VERSION}#${it.FRAMEWORK}"}
  def matrix = [:]
  frameworks.each{ fw ->
    def key = "${py}#${fw}"
    if(!excludes.contains(key)){
      matrix[key] = [python: py, framework: fw]
    }
  }
  return matrix
}