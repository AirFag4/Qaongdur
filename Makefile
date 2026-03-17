SHELL := /bin/bash
ENV_FILE := $(shell if [ -f .env ]; then echo .env; else echo .env.example; fi)
CORE_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml --profile core
VISION_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml --profile core --profile mock-video --profile face --profile vision-cpu
FACE_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml --profile core --profile face
MOCK_VIDEO_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml --profile core --profile mock-video
DISTRO_CENTRAL_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml -f infra/docker/compose.distributed-central.yml --profile core --profile mock-video --profile vision-api
DISTRO_MOCK_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml -f infra/docker/compose.distributed-central.yml -f infra/docker/compose.worker.yml --profile core --profile mock-video --profile vision-api --profile vision-worker-cpu
AUTH_COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker/compose.auth.yml

.PHONY: setup submodules dev lint test build docker-up docker-auth-up docker-down logs seed vision-up face-up mock-video-up mock-stream-up distributed-central-up distributed-mock-up

setup:
	git submodule update --init --recursive
	pnpm install

submodules:
	git submodule update --init --recursive

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
	docker compose --env-file $(ENV_FILE) -f infra/docker/compose.core.yml --profile core --profile mock-video --profile mock-stream --profile face --profile vision-cpu --profile vision-gpu --profile nvr-local down --remove-orphans

logs:
	$(CORE_COMPOSE) logs -f --tail=200

seed:
	$(CORE_COMPOSE) run --rm object-storage-bootstrap

vision-up:
	$(VISION_COMPOSE) up -d --build

face-up:
	$(FACE_COMPOSE) up -d --build face-api

mock-video-up:
	$(MOCK_VIDEO_COMPOSE) up -d --build mock-streamer

mock-stream-up:
	$(MOCK_VIDEO_COMPOSE) up -d --build mock-streamer

distributed-central-up:
	$(DISTRO_CENTRAL_COMPOSE) up -d --build

distributed-mock-up:
	$(DISTRO_MOCK_COMPOSE) up -d --build
