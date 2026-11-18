SHELL := /bin/bash
COMPOSE ?= docker compose

.DEFAULT_GOAL := help

.PHONY: help up down logs test reset-db ps build config

help:
	@echo "DepaFix - comandos disponibles:"
	@echo "  make up        Levanta api + db + frontend (build incluido)"
	@echo "  make down      Detiene y elimina los contenedores"
	@echo "  make logs      Sigue los logs de todos los servicios"
	@echo "  make test      Valida import de la app y docker-compose.yml"
	@echo "  make reset-db  Borra el volumen de Postgres y recrea la db"
	@echo "  make ps        Muestra el estado de los servicios"
	@echo "  make build     Construye las imágenes sin levantar"
	@echo "  make config    Valida la configuración de Docker Compose"

up:
	@test -f .env || (cp .env.example .env && echo "Creado .env desde .env.example. Edita las credenciales reales.")
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

test:
	@test -f .env || cp .env.example .env
	@if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi; \
		$$PY -c "from app.main import app; print('OK: app importada correctamente')"
	@$(COMPOSE) config -q
	@echo "OK: docker-compose.yml válido"

reset-db:
	$(COMPOSE) down -v && $(COMPOSE) up -d db

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

config:
	$(COMPOSE) config
