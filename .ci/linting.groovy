#!/usr/bin/env groovy
@Library('apm@current') _

pipeline {
  agent { label 'linux && immutable' }
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
    issueCommentTrigger('(?i).*(?:jenkins\\W+)?run\\W+(?:the\\W+)?linters(?:\\W+please)?.*')
  }
  stages {
    stage('Sanity checks') {
      steps {
        script {
          def sha = getGitCommitSha()
          echo 'For debugging purposes in the host'
          sh 'env | sort'
          docker.image('python:3.7-stretch').inside("-e PATH=${PATH}:${env.WORKSPACE}/bin"){
            echo 'For debugging purposes within the docker container.'
            sh 'env | sort'
            // registry: '' will help to disable the docker login
            preCommit(commit: "${sha}", junit: true, registry: '')
          }
        }
      }
    }
  }
}
