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
  agent any
  environment {
    REPO="git@github.com:elastic/apm-agent-python.git"
    BASE_DIR="src/github.com/elastic/apm-agent-python"
    PIPELINE_LOG_LEVEL='INFO'
    NOTIFY_TO = credentials('notify-to')
    JOB_GCS_BUCKET = credentials('gcs-bucket')
    CODECOV_SECRET = 'secret/apm-team/ci/apm-agent-python-codecov'
    JOB_GIT_CREDENTIALS = "f6c7695a-671e-4f4f-a331-acdce44ff9ba"
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
  parameters {
    string(name: 'PYTHON_VERSION', defaultValue: "python-3.6", description: "Python version to test")
    string(name: 'BRANCH_SPECIFIER', defaultValue: "", description: "Git branch/tag to use")
    string(name: 'MERGE_TARGET', defaultValue: "", description: "Git branch/tag to merge before building")
  }
  stages {
    /**
    Checkout the code and stash it, to use it on other stages.
    */
    stage('Checkout') {
      agent { label 'docker && linux && immutable' }
      options { skipDefaultCheckout() }
      steps {
        if(params.CHANGE_TARGET == null || params.BRANCH_SPECIFIER == null){
          error("Invalid job parameters")
        }
        deleteDir()
        gitCheckout(basedir: "${BASE_DIR}",
          branch: "${params.BRANCH_SPECIFIER}",
          repo: "${REPO}",
          credentialsId: "${JOB_GIT_CREDENTIALS}",
          mergeTarget: "${params.MERGE_TARGET}"
          reference: '/var/lib/jenkins/apm-agent-python.git')
        stash allowEmpty: true, name: 'source', useDefaultExcludes: false
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
              xVersions: [ "${PYTHON_VERSION}" ],
              yKey: 'FRAMEWORK',
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
  post {
    always{
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
        notifyBuildResult()
      }
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
  build a clousure that launch and agent and execute the corresponding test script,
  then store the results.
  */
  public Closure generateStep(x, y){
    return {
      steps.node('linux && immutable'){
        def label = "${tag}-${x}-${y}"
        try {
          steps.runScript(label: label, python: x, framework: y)
          saveResult(x, y, 1)
        } catch(e){
          saveResult(x, y, 0)
          error("${label} tests failed : ${e.toString()}\n")
        } finally {
          wrappingUp()
        }
      }
    }
  }
}

def runScript(Map params = [:]){
  log(level: 'INFO', text: "${params.label}")
  env.HOME = "${env.WORKSPACE}"
  env.PATH = "${env.PATH}:${env.WORKSPACE}/bin"
  env.PIP_CACHE = "${env.WORKSPACE}/.cache"
  deleteDir()
  sh "mkdir ${env.PIP_CACHE}"
  unstash 'source'
  dir("${BASE_DIR}"){
    retry(2){
      sleep randomNumber(min:10, max: 30)
      sh("./tests/scripts/docker/run_tests.sh ${params.python} ${params.framework}")
    }
  }
}

/**
  Collect test results and report to Codecov
*/
def wrappingUp(){
  junit(allowEmptyResults: false, keepLongStdio: true,
      testResults: "**/python-agent-junit.xml,**/target/**/TEST-*.xml")
  env.PYTHON_VERSION = "${x}"
  env.WEBFRAMEWORK = "${y}"
  codecov(repo: 'apm-agent-python', basedir: "${BASE_DIR}",
      flags: "-e PYTHON_VERSION,WEBFRAMEWORK",
      secret: "${CODECOV_SECRET}")
}
