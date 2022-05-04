#!/usr/bin/env groovy
@Library('apm@current') _

pipeline {
  agent { label 'linux && immutable' }
  environment {
    BASE_DIR = "src"
    HOME = "${env.WORKSPACE}/${env.BASE_DIR}"
  }
  options {
    buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '20', daysToKeepStr: '30'))
    timestamps()
    ansiColor('xterm')
    disableResume()
    durabilityHint('PERFORMANCE_OPTIMIZED')
    rateLimitBuilds(throttle: [count: 60, durationName: 'hour', userBoost: true])
    quietPeriod(10)
  }
  triggers {
    issueCommentTrigger('(?i)(/test).linters.*')
  }
  stages {
    stage('Checkout') {
      options { skipDefaultCheckout() }
      steps {
        runCheckout()
      }
    }
    stage('Sanity checks') {
      options { skipDefaultCheckout() }
      steps {
        dir("${BASE_DIR}") {
          runPreCommit()
        }
      }
    }
  }
}

def runCheckout() {
  // Use gitCheckout to prepare the context
  try {
    gitCheckout(basedir: "${BASE_DIR}", githubNotifyFirstTimeContributor: false)
  } catch (err) {
    // NOOP: avoid failing if non-elasticians, this will avoid issues when PRs comming
    //       from non elasticians since the validation will not fail
  }
}

def runPreCommit() {
  docker.image('python:3.7-stretch').inside(){
    // registry: '' will help to disable the docker login
    preCommit(commit: "${GIT_BASE_COMMIT}", junit: true, registry: '')
  }
}
