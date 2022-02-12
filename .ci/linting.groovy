#!/usr/bin/env groovy
@Library('apm@current') _

pipeline {
  agent { kubernetes { yamlFile '.ci/k8s/PythonPod.yml' } }
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
        container('python-3-7') {
          // registry: '' will help to disable the docker login
          preCommit(commit: getGitCommitSha(), junit: true, registry: '')
        }
      }
    }
  }
}
