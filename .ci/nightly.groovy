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
    HOME = "${env.WORKSPACE}"
    PATH = "${env.PATH}:${env.WORKSPACE}/bin"
    PIP_CACHE = "${env.WORKSPACE}/.cache"
  }
  options {
    timeout(time: 3, unit: 'HOURS')
    buildDiscarder(logRotator(numToKeepStr: '100', artifactNumToKeepStr: '100', daysToKeepStr: '100'))
    timestamps()
    ansiColor('xterm')
    disableResume()
    durabilityHint('PERFORMANCE_OPTIMIZED')
    rateLimitBuilds(throttle: [count: 60, durationName: 'hour', userBoost: true])
    quietPeriod(10)
  }
  triggers {
    cron 'H 02 * * *'
  }
  stages {
    stage('Initializing'){
      options { skipDefaultCheckout() }
      stages {
        stage('Checkout') {
          steps {
            deleteDir()
            gitCheckout(basedir: "${BASE_DIR}", githubNotifyFirstTimeContributor: true)
            stash allowEmpty: true, name: 'source', useDefaultExcludes: false
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
                xFile: ".ci/.jenkins_python_full.yml",
                yFile: ".ci/.jenkins_framework_full.yml",
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
  deleteDir()
  sh "mkdir ${env.PIP_CACHE}"
  unstash 'source'
  dir("${BASE_DIR}"){
    withEnv([
      "LOCAL_USER_ID=${sh(script:'id -u', returnStdout: true).trim()}",
      "LOCAL_GROUP_ID=${sh(script:'id -g', returnStdout: true).trim()}",
      "LOCALSTACK_VOLUME_DIR=localstack_data"
    ]) {
      retryWithSleep(retries: 2, seconds: 5, backoff: true) {
        sh("./tests/scripts/docker/run_tests.sh ${python} ${framework}")
      }
    }
  }
}
