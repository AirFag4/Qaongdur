SHELL := /bin/bash
ENV_FILE := $(shell if [ -f .env ]; then echo .env; else echo .env.example; fi)
CORE_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml --profile core
VISION_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml --profile core --profile vision-cpu
AUTH_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.auth.yml

.PHONY: setup dev lint test build docker-up docker-auth-up docker-down logs seed vision-up

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
	$(CORE_COMPOSE) up -d --build

docker-auth-up:
	$(AUTH_COMPOSE) up -d

docker-down:
	docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml --profile core --profile vision-cpu --profile vision-gpu --profile nvr-local down --remove-orphans

logs:
	$(CORE_COMPOSE) logs -f --tail=200

seed:
	$(CORE_COMPOSE) run --rm object-storage-bootstrap

vision-up:
	$(VISION_COMPOSE) up -d --build
