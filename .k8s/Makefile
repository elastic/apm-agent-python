SHELL = /bin/bash
ARCH = $(shell uname)
ARCH_L = $(shell uname|tr '[:upper:]' '[:lower:]')
BIN_DIR ?= $(CURDIR)/bin
KUBECTL_VERSION ?= $(shell curl -sSf https://storage.googleapis.com/kubernetes-release/release/stable.txt)
KUBECTL ?= $(BIN_DIR)/kubectl
SKAFFOLD ?= $(BIN_DIR)/skaffold
PATH := $(BIN_DIR):$(PATH)
#MAKEFLAGS += --silent --no-print-directory
.SHELLFLAGS = -ec
GIT_USERNAME ?= $(shell git config user.name | tr -d ' '| tr '[:upper:]' '[:lower:]')

.SILENT:

# Whether to run all the python versions from the whole support matrix
FULL ?= false
# TODO: allow dynamism so the cluster is defined in Vault maybe?
K8S_CLUSTER ?= observability-ci-test-k8s
K8S_NAMESPACE ?= $(GIT_USERNAME)
# TODO: allow dynamism so the cluster is defined in Vault maybe?
# TODO: GCLOUD specific, maybe it wont't be needed if we are cloud agnostic?
GCLOUD_K8S_CLUSTER_REGION ?= us-central1-c
# TODO: allow dynamism so the cluster is defined in Vault maybe?
# TODO: GCLOUD specific, maybe it wont't be needed if we are cloud agnostic?
GCLOUD_K8S_CLUSTER_PROJECT ?= elastic-observability
DEFAULT_REPO ?= docker.elastic.co/beats-dev

EXCLUDE = .ci/.jenkins_exclude.yml
ifeq ($(FULL), true)
FRAMEWORKS = .ci/.jenkins_framework_full.yml
VERSIONS = .ci/.jenkins_python_full.yml
else
FRAMEWORKS = .ci/.jenkins_framework.yml
VERSIONS = .ci/.jenkins_python.yml
endif


################################
## Helper function
################################
.PHONY: help
help:
	@echo "Environment variables:"
	@echo ""
	@echo 'VAULT_TOKEN=$$(cat $${HOME}/.vault-token) this token is needed for local operations'
	@echo ""
	@echo "Main targets:"
	@echo ""
	@grep '^## @help' Makefile|cut -d ":" -f 2-3|( (sort|column -s ":" -t) || (sort|tr ":" "\t") || (tr ":" "\t"))

################################
## Tools helper functions
################################
bin:
	mkdir -p "$(BIN_DIR)"

## @help:bin/kubectl:Install kubectl CLI in the selected binary folder.
bin/kubectl: bin
	curl -sSLo "$(KUBECTL)" "https://storage.googleapis.com/kubernetes-release/release/$(KUBECTL_VERSION)/bin/$(ARCH_L)/amd64/kubectl"
	chmod +x "$(KUBECTL)

## @help:bin/skaffold:Install skaffold CLI in the selected binary folder.
bin/skaffold: bin
	curl -sSLo "$(SKAFFOLD)" "https://storage.googleapis.com/skaffold/releases/latest/skaffold-$(ARCH_L)-amd64"
	chmod +x "$(SKAFFOLD)"

setup: bin/kubectl bin/skaffold

################################
## K8s specific helper functions
################################

## @help:k8s-login:Get the credentials of the k8s cluster.
.PHONY: k8s-login
k8s-login:
	@gcloud container clusters get-credentials \
		--zone $(GCLOUD_K8S_CLUSTER_REGION) \
		--project $(GCLOUD_K8S_CLUSTER_PROJECT) \
		$(K8S_CLUSTER)
	$(KUBECTL) config set-context $$(kubectl config current-context) --namespace $(K8S_NAMESPACE)

## @help:k8s-create-namespace:Create the k8s namespace.
k8s-create-namespace:
	$(KUBECTL) create namespace $(K8S_NAMESPACE)

# @help:get-pods:Get the deployed pods in the K8s cluster
.PHONY: get-pods
get-pods:
	$(KUBECTL) get pods -n $(K8S_NAMESPACE)

# @help:get-pods:Get the deployed pods in the K8s cluster
.PHONY: get-jobs
get-jobs:
	$(KUBECTL) get job.batch -n $(K8S_NAMESPACE)

################################
## Skaffold specific helper functions
################################
# @help:skaffold-docker-base:Generate the docker base image
skaffold-docker-base:
	for number in "3.6" "3.7" "3.8" "3.9" "3.10" ; do \
		$(MAKE) skaffold-base-$$number ; \
	done

skaffold-base-%:
	cd ../tests; \
	docker build --build-arg PYTHON_IMAGE=python:$* -t $(DEFAULT_REPO)/apm-agent-python:$* . ; \
	docker push $(DEFAULT_REPO)/apm-agent-python:$*

# @help:skaffold-deploy:Deploy the pods
skaffold-deploy:
	cd ..; \
	$(SKAFFOLD) deploy \
		--default-repo=$(DEFAULT_REPO) \
		--build-artifacts=$(CURDIR)/tags.json \
		--namespace=$(K8S_NAMESPACE) \
		--label=user.repo=$(GIT_USERNAME) -p flask-1.1

# @help:skaffold-deploy-%:Deploy the pods for the given framework
skaffold-deploy-%:
	cd ..; \
	$(SKAFFOLD) deploy \
		--default-repo=$(DEFAULT_REPO) \
		--build-artifacts=$(CURDIR)/tags.json \
		--namespace=$(K8S_NAMESPACE) \
		--label=user.repo=$(GIT_USERNAME) -p $*

# @help:skaffold-test:Run the tests in the deployed pods and report the results.
skaffold-test: skaffold-deploy skaffold-wait

# @help:skaffold-test-%:Run the tests in the deployed pods and report the results for the given framework
skaffold-test-%:
	$(MAKE) skaffold-deploy-$* skaffold-wait

# @help:skaffold-deploy:Deploy the pods
skaffold-render:
	cd ..; \
	$(SKAFFOLD) render \
		--default-repo=$(DEFAULT_REPO) \
		--build-artifacts=$(CURDIR)/tags.json \
		--namespace=$(K8S_NAMESPACE) \
		--label=user.repo=$(GIT_USERNAME) -p flask-1.1

# @help:skaffold-wait:Report the results.
skaffold-wait:
	K8S_NAMESPACE=$(K8S_NAMESPACE) \
	GIT_USERNAME=$(GIT_USERNAME) \
	$(CURDIR)/wait.sh
