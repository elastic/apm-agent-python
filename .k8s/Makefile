SHELL = /bin/bash
ARCH = $(shell uname)
ARCH_L = $(shell uname|tr '[:upper:]' '[:lower:]')
BIN_DIR ?= $(CURDIR)/bin
KUBECTL_VERSION ?= $(shell curl -sSf https://storage.googleapis.com/kubernetes-release/release/stable.txt)
KUBECTL ?= $(BIN_DIR)/kubectl
SKAFFOLD ?= skaffold
PATH := $(BIN_DIR):$(PATH)
MAKEFLAGS += --silent --no-print-directory
.SHELLFLAGS = -ec
GIT_USERNAME ?= $(shell git config user.name | tr -d ' ')

.SILENT:

# TODO: allow dynamism so the cluster is defined in Vault maybe?
K8S_CLUSTER ?= observability-ci-test-k8s
K8S_NAMESPACE ?= default
K8S_POD_NAME ?= python-versions-pod
# TODO: allow dynamism so the cluster is defined in Vault maybe?
# TODO: GCLOUD specific, maybe it wont't be needed if we are cloud agnostic?
GCLOUD_K8S_CLUSTER_REGION ?= us-central1-c
# TODO: allow dynamism so the cluster is defined in Vault maybe?
# TODO: GCLOUD specific, maybe it wont't be needed if we are cloud agnostic?
GCLOUD_K8S_CLUSTER_PROJECT ?= elastic-observability
DEFAULT_REPO ?= docker.elastic.co/beats-dev

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
	curl -sSLo "$(BIN_DIR)/kubectl" "https://storage.googleapis.com/kubernetes-release/release/$(KUBECTL_VERSION)/bin/$(ARCH_L)/amd64/kubectl"
	chmod +x "$(BIN_DIR)/kubectl"

setup: bin/kubectl

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

# @help:deploy-pods:Deploy the pods in the K8s cluster
.PHONY: deploy-pods
deploy-pods:
	$(KUBECTL) apply -f PythonPod.yml

# @help:undeploy-pods:Deploy the pods in the K8s cluster
.PHONY: undeploy-pods
undeploy-pods: k8s-login
	$(KUBECTL) delete -f PythonPod.yml

# @help:get-pods:Get the deployed pods in the K8s cluster
.PHONY: deploy-pods
get-pods:
	$(KUBECTL) get pods
	$(KUBECTL) describe pod $(K8S_POD_NAME)

# @help:ssh-pod:Interactive shell with the default pod
ssh-default-pod:
	$(KUBECTL) exec --stdin --tty $(K8S_POD_NAME) -- /bin/bash

# @help:ssh-pod:Interactive shell in the given container
ssh-pod-%:
	$(KUBECTL) exec --stdin --tty $(K8S_POD_NAME) --container $* -- /bin/bash

# @help:sync-pods:Sync workspace with the pods
sync-pods:
	$(KUBECTL) cp ./ $(K8S_POD_NAME):/src

################################
## Skaffold specific helper functions
################################

# @help:skaffold-build:Sync workspace with the pods
skaffold-build:
	cd ..; \
	$(SKAFFOLD) build \
		--default-repo=$(DEFAULT_REPO) \
		--file-output=$(CURDIR)/tags.json

# @help:skaffold-deploy:Deploy the pods
skaffold-deploy:
	cd ..; \
	$(SKAFFOLD) deploy \
		--default-repo=$(DEFAULT_REPO) \
		--build-artifacts=$(CURDIR)/tags.json \
		--namespace=$(K8S_NAMESPACE) \
		--label=user.repo=$(GIT_USERNAME)

# @help:skaffold-test:Run the tests in the deployed pods and report the results.
skaffold-test: skaffold-deploy
	K8S_NAMESPACE=$(K8S_NAMESPACE) \
	GIT_USERNAME=$(GIT_USERNAME) \
	$(CURDIR)/wait.sh
