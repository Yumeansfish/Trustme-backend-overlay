SHELL := /usr/bin/env bash

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

ifneq ("$(wildcard $(REPO_ROOT)/../upstream/activitywatch)","")
DEFAULT_UPSTREAM_DIR := $(REPO_ROOT)/../upstream/activitywatch
DEFAULT_BUILD_ROOT := $(REPO_ROOT)/../upstream/build
else
DEFAULT_UPSTREAM_DIR := $(REPO_ROOT)/upstream/activitywatch
DEFAULT_BUILD_ROOT := $(REPO_ROOT)/upstream/build
endif

ifneq ("$(wildcard $(REPO_ROOT)/../frontend)","")
DEFAULT_FRONTEND_DIR := $(REPO_ROOT)/../frontend
else
DEFAULT_FRONTEND_DIR := $(REPO_ROOT)/frontend
endif

UPSTREAM_DIR ?= $(DEFAULT_UPSTREAM_DIR)
FRONTEND_DIR ?= $(DEFAULT_FRONTEND_DIR)
BUILD_ROOT ?= $(DEFAULT_BUILD_ROOT)
APP_PATH ?= /Applications/trust-me.app

.PHONY: release build-bundle build-release render-site sync-app sync-survey-videos

release: build-release

build-bundle:
	UPSTREAM_DIR="$(UPSTREAM_DIR)" \
	FRONTEND_DIR="$(FRONTEND_DIR)" \
	BUILD_ROOT="$(BUILD_ROOT)" \
	RELEASE_VERSION="$(RELEASE_VERSION)" \
	./scripts/release/build_browser_line_bundle.sh

render-site:
	python3 ./scripts/release/render_release_site.py \
		--metadata "$(BUILD_ROOT)/dist/release-metadata.json" \
		--output-dir "$(BUILD_ROOT)/site" \
		--repository "$${GITHUB_REPOSITORY:-Yumeansfish/Trustme-backend-overlay}" \
		--release-tag "$${SITE_RELEASE_TAG:-latest}"

build-release: build-bundle render-site

sync-app: build-bundle
	./scripts/release/sync_browser_line_into_app.sh \
		"$(BUILD_ROOT)/dist/browser-line" \
		"$(APP_PATH)"

sync-survey-videos:
	python3 ./scripts/sync_survey_videos.py \
		--remote-host "$${REMOTE_HOST:-uc-workstation}" \
		--remote-dir "$${REMOTE_DIR:-~/highlights}" \
		$${LOCAL_DIR:+--local-dir "$$LOCAL_DIR"}
