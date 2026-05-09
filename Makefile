SHELL := /bin/bash

DC := docker compose
PROD_DC := docker compose -f docker-compose.yml -f docker-compose.prod.yml
API_RUN := $(DC) run --rm api

ROLE ?= viewer
BASE_URL ?= http://localhost:3001

.PHONY: help build start stop restart status logs prod-build prod-start prod-stop prod-restart prod-status prod-logs user-add user-delete user-list user-set-password user-reset-link

help:
	@echo "Targets:"
	@echo "  make build"
	@echo "  make start"
	@echo "  make stop"
	@echo "  make restart"
	@echo "  make status"
	@echo "  make logs"
	@echo "  make prod-build"
	@echo "  make prod-start"
	@echo "  make prod-stop"
	@echo "  make prod-restart"
	@echo "  make prod-status"
	@echo "  make prod-logs"
	@echo "  make user-add USERNAME=<user> PASSWORD=<pass> [ROLE=viewer|admin]"
	@echo "  make user-delete USERNAME=<user>"
	@echo "  make user-list"
	@echo "  make user-set-password USERNAME=<user> PASSWORD=<pass>"
	@echo "  make user-reset-link USERNAME=<user> [BASE_URL=http://localhost:3001]"

build:
	$(DC) build

start:
	$(DC) up -d

stop:
	$(DC) down

restart:
	$(DC) up -d --build

status:
	$(DC) ps

logs:
	$(DC) logs -n 100 -f

prod-build:
	$(PROD_DC) build

prod-start:
	$(PROD_DC) up -d

prod-stop:
	$(PROD_DC) down

prod-restart:
	$(PROD_DC) up -d --build

prod-status:
	$(PROD_DC) ps

prod-logs:
	$(PROD_DC) logs -f

user-add:
	@test -n "$(USERNAME)" || (echo "USERNAME is required"; exit 1)
	@test -n "$(PASSWORD)" || (echo "PASSWORD is required"; exit 1)
	$(API_RUN) python -m scripts.create_user --username "$(USERNAME)" --password "$(PASSWORD)" --role "$(ROLE)"

user-delete:
	@test -n "$(USERNAME)" || (echo "USERNAME is required"; exit 1)
	$(API_RUN) python -m scripts.delete_user --username "$(USERNAME)"

user-list:
	$(API_RUN) python -m scripts.list_users

user-set-password:
	@test -n "$(USERNAME)" || (echo "USERNAME is required"; exit 1)
	@test -n "$(PASSWORD)" || (echo "PASSWORD is required"; exit 1)
	$(API_RUN) python -m scripts.set_password --username "$(USERNAME)" --password "$(PASSWORD)"

user-reset-link:
	@test -n "$(USERNAME)" || (echo "USERNAME is required"; exit 1)
	$(API_RUN) python -m scripts.create_reset_token --username "$(USERNAME)" --base-url "$(BASE_URL)" $(if $(PRINT_URL),--print-url,)
