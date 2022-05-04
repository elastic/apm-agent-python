#!/usr/bin/env groovy
@Library('apm@current') _

pipeline {
  agent { label 'linux && immutable' }
  environment {
    HOME = "${env.WORKSPACE}"
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
    stage('Sanity checks') {
      steps {
        script {
          // Since gitCheckout is not used, then it's required to call the GitHub environment
          // variables creation.
          githubEnv()
          docker.image('python:3.7-stretch').inside(){
            // registry: '' will help to disable the docker login
            preCommit(commit: "${GIT_BASE_COMMIT}", junit: true, registry: '')
          }
        }
      }
    }
  }
}
