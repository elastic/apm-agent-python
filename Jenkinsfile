#!/usr/bin/env groovy
@Library('apm@current') _

import co.elastic.matrix.*
import groovy.transform.Field

pipeline {
  agent { label 'linux-immutable && ubuntu-20' }
  environment {
    REPO = 'apm-agent-python'
    BASE_DIR = "src/github.com/elastic/${env.REPO}"
    PIPELINE_LOG_LEVEL='INFO'
    NOTIFY_TO = credentials('notify-to')
    JOB_GCS_BUCKET = credentials('gcs-bucket')
    CODECOV_SECRET = 'secret/apm-team/ci/apm-agent-python-codecov'
    BENCHMARK_SECRET  = 'secret/apm-team/ci/benchmark-cloud'
    OPBEANS_REPO = 'opbeans-python'
    HOME = "${env.WORKSPACE}"
    PIP_CACHE = "${env.WORKSPACE}/.cache"
    SLACK_CHANNEL = '#apm-agent-python'
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
    issueCommentTrigger("(${obltGitHubComments()}).?(full|benchmark)?")
  }
  parameters {
    booleanParam(name: 'Run_As_Main_Branch', defaultValue: false, description: 'Allow to run any steps on a PR, some steps normally only run on main branch.')
    booleanParam(name: 'bench_ci', defaultValue: true, description: 'Enable benchmarks.')
    booleanParam(name: 'tests_ci', defaultValue: true, description: 'Enable tests.')
    booleanParam(name: 'package_ci', defaultValue: true, description: 'Enable building packages.')
  }
  stages {
    stage('Initializing'){
      options {
        skipDefaultCheckout()
        timeout(time: 1, unit: 'HOURS')
      }
      stages {
        /**
        Checkout the code and stash it, to use it on other stages.
        */
        stage('Checkout') {
          steps {
            pipelineManager([ cancelPreviousRunningBuilds: [ when: 'PR' ] ])
            deleteDir()
            gitCheckout(basedir: "${BASE_DIR}", githubNotifyFirstTimeContributor: true)
            stash allowEmpty: true, name: 'source', useDefaultExcludes: false
            script {
              dir("${BASE_DIR}"){
                // Skip all the stages except docs for PR's with asciidoc and md changes only
                env.ONLY_DOCS = isGitRegionMatch(patterns: [ '.*\\.(asciidoc|md)' ], shouldMatchAll: true)
              }
            }
          }
        }
        stage('Benchmarks') {
          agent { label 'microbenchmarks-pool' }
          options { skipDefaultCheckout() }
          environment {
            AGENT_WORKDIR = "${env.WORKSPACE}/${env.BUILD_NUMBER}/${env.BASE_DIR}"
            LANG = 'C.UTF-8'
            LC_ALL = "${env.LANG}"
            PATH = "${env.WORKSPACE}/.local/bin:${env.WORKSPACE}/bin:${env.PATH}"
          }
          when {
            beforeAgent true
            allOf {
              anyOf {
                branch 'main'
                expression { return params.Run_As_Main_Branch }
                expression { return env.GITHUB_COMMENT?.contains('benchmark') }
              }
              expression { return params.bench_ci }
            }
          }
          steps {
            withGithubNotify(context: 'Benchmarks', tab: 'artifacts') {
              dir(env.BUILD_NUMBER) {
                deleteDir()
                unstash 'source'
                script {
                  dir(BASE_DIR){
                    sendBenchmarks.prepareAndRun(secret: env.BENCHMARK_SECRET, url_var: 'ES_URL',
                                                user_var: 'ES_USER', pass_var: 'ES_PASS') {
                      sh 'scripts/run-benchmarks.sh "${AGENT_WORKDIR}" "${ES_URL}" "${ES_USER}" "${ES_PASS}"'
                    }
                  }
                }
              }
            }
          }
          post {
            always {
              catchError(message: 'deleteDir failed', buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                deleteDir()
              }
            }
          }
        }
      }
    }
  }
}
