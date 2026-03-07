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
	@ENV_FILE=infra/docker/.env; \
	if [ ! -f "$$ENV_FILE" ]; then ENV_FILE=infra/docker/.env.example; fi; \
	docker compose --env-file "$$ENV_FILE" -f infra/docker/compose.auth.yml up -d
