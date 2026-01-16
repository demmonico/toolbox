# import config.
# You can change the default config with `make cnf="config_special.env" build`
cnf ?= .env
-include $(cnf)
# check if the env file exists
ifneq ("$(wildcard "$(cnf)")","")
	export $(shell sed 's/=.*//' $(cnf))
endif

# HELP
# This will output the help for each task
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
.PHONY: help

help: ## This help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help

#------------------------------------------------------------------------------#

tag ?= latest
image ?= "demmonico/toolbox:$(tag)"

build: ## Build the docker image
	@docker buildx build --platform linux/amd64,linux/arm64 -t $(image) .
	@echo ""
	docker image ls | grep -E '(IMAGE|toolbox)'
	@echo ""

push: ## Push the docker image
	@docker login
	@echo ""
	@docker push $(image)

run-helper: ## Run the MySQL Locks Helper script
	@docker run --rm -it $(image) python mysql-locks-helper.py

ping: ## Run the container
	@docker run --rm -it $(image) ping google.com

run: ## Run the container
	@docker run --rm -it $(image) $(filter-out $@,$(MAKECMDGOALS))

# Catch-all target to prevent "No rule to make target" errors (required for `make run <command>`)
%:
	@:
