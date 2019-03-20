#!/usr/bin/env groovy
@Library('apm@v1.0.6') _

import co.elastic.matrix.*
import groovy.transform.Field

/**
This is the parallel tasks generator,
it is need as field to store the results of the tests.
*/
@Field def pythonTasksGen

pipeline {
  agent any
  environment {
    BASE_DIR="src/github.com/elastic/apm-agent-python"
    PIPELINE_LOG_LEVEL='INFO'
    NOTIFY_TO = credentials('notify-to')
    JOB_GCS_BUCKET = credentials('gcs-bucket')
  }
  options {
    timeout(time: 1, unit: 'HOURS')
    buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '20', daysToKeepStr: '30'))
    timestamps()
    ansiColor('xterm')
    disableResume()
    durabilityHint('PERFORMANCE_OPTIMIZED')
  }
  triggers {
    issueCommentTrigger('.*(?:jenkins\\W+)?run\\W+(?:the\\W+)?tests(?:\\W+please)?.*')
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
          }
        }
        /**
        Build the project from code..
        */
        stage('Lint') {
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
      agent { label 'linux && immutable' }
      options { skipDefaultCheckout() }
      steps {
        deleteDir()
        unstash "source"
        dir("${BASE_DIR}"){
          script {
            pythonTasksGen = new PythonParallelTaskGenerator(
              xKey: 'PYTHON_VERSION',
              yKey: 'FRAMEWORK',
              xFile: "./tests/.jenkins_python.yml",
              yFile: "./tests/.jenkins_framework.yml",
              exclusionFile: "./tests/.jenkins_exclude.yml",
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
            expression { return params.Run_As_Master_Branch }
          }
          expression { return params.doc_ci }
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
    always{
      script{
        if(pythonTasksGen?.results){
          writeJSON(file: 'results.json', json: toJSON(pythonTasksGen.results), pretty: 2)
          def mapResults = ["${params.agent_integration_test}": pythonTasksGen.results]
          def processor = new ResultsProcessor()
          processor.processResults(mapResults)
          archiveArtifacts allowEmptyArchive: true, artifacts: 'results.json,results.html', defaultExcludes: false
        }
      }
    }
    success {
      echoColor(text: '[SUCCESS]', colorfg: 'green', colorbg: 'default')
    }
    aborted {
      echoColor(text: '[ABORTED]', colorfg: 'magenta', colorbg: 'default')
    }
    failure {
      echoColor(text: '[FAILURE]', colorfg: 'red', colorbg: 'default')
      step([$class: 'Mailer', notifyEveryUnstableBuild: true, recipients: "${NOTIFY_TO}", sendToIndividuals: false])
    }
    unstable {
      echoColor(text: '[UNSTABLE]', colorfg: 'yellow', colorbg: 'default')
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
            error("${label} tests failed : ${e.toString()}\n")
          } finally {
            steps.junit(allowEmptyResults: false,
              keepLongStdio: true,
              testResults: "**/python-agent-junit.xml,**/target/**/TEST-*.xml")
            steps.env.PYTHON_VERSION = "${x}"
            steps.env.WEBFRAMEWORK = "${y}"
            steps.codecov(repo: 'apm-agent-python',
              basedir: "${steps.env.BASE_DIR}",
              flags: "-e PYTHON_VERSION,WEBFRAMEWORK")
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
