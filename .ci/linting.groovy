#!/usr/bin/env groovy
@Library('apm@current') _

pipeline {
  agent none
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
    issueCommentTrigger('(?i).*(?:jenkins\\W+)?run\\W+(?:the\\W+)?lint(?:\\W+please)?.*')
  }
  stages {
    stage('Sanity checks') {
      agent { label 'docker && linux && immutable' }
      environment {
        HOME = "${env.WORKSPACE}"
        PATH = "${env.PATH}:${env.WORKSPACE}/bin"
      }
      steps {
        script {
          def sha = getGitCommitSha()
          docker.image('python:3.7-stretch').inside("-e PATH=${PATH}:${env.WORKSPACE}/bin"){
            // registry: '' will help to disable the docker login
            preCommit(commit: "${sha}", junit: true, registry: '')
          }
        }
      }
    }
  }
}
