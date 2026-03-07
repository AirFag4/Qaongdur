SHELL := /bin/bash

.PHONY: setup dev lint test build docker-up

setup:
	pnpm install

dev:
	pnpm --filter @qaongdur/web dev

lint:
	pnpm -r --if-present lint

test:
	pnpm -r --if-present test

build:
	pnpm -r --if-present build

docker-up:
	@echo "Docker compose setup is planned for infra/docker in a later phase."
