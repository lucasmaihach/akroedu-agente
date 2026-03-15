.PHONY: help install setup up down logs test clean new-course

help:
	@echo "🤖 Sales Agent — Pós-Graduação"
	@echo ""
	@echo "Comandos disponíveis:"
	@echo "  make install                        - Instala dependências Python"
	@echo "  make setup                          - Setup inicial (cria .env, inicia containers)"
	@echo "  make up                             - Sobe os containers"
	@echo "  make down                           - Para os containers"
	@echo "  make logs                           - Mostra logs da API em tempo real"
	@echo "  make logs-postgres                  - Logs do PostgreSQL"
	@echo "  make logs-redis                     - Logs do Redis"
	@echo "  make shell-api                      - Entra no shell do container API"
	@echo "  make shell-postgres                 - Entra no PostgreSQL"
	@echo "  make test                           - Roda testes"
	@echo "  make test-webhook                   - Testa webhook localmente"
	@echo "  make upload-audios                  - Faz upload dos áudios para a Meta"
	@echo "  make test-agents                    - Testa os agentes"
	@echo "  make clean                          - Remove containers e volumes"
	@echo "  make rebuild                        - Reconstrói as imagens"
	@echo "  make new-course slug=X name=Y consultant=Z  - Cria novo curso"
	@echo ""
	@echo "Exemplo para criar novo curso:"
	@echo "  make new-course slug=mba_direito name='MBA em Direito' consultant=Roberto"
	@echo ""

install:
	pip install -r requirements.txt

setup:
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "✅ Arquivo .env criado. Edite com suas credenciais: nano .env"; \
	fi
	docker-compose up -d
	@echo "✅ Containers iniciados!"

up:
	docker-compose up -d
	@echo "✅ Containers rodando"

down:
	docker-compose down
	@echo "✅ Containers parados"

logs:
	docker-compose logs -f api

logs-postgres:
	docker-compose logs -f postgres

logs-redis:
	docker-compose logs -f redis

shell-api:
	docker-compose exec api /bin/bash

shell-postgres:
	docker-compose exec postgres psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

test:
	pytest tests/ -v --tb=short

test-webhook:
	chmod +x test_webhook.sh
	./test_webhook.sh http://localhost:8000 5511999999999

test-agents:
	python scripts/test_agents.py

upload-audios:
	@which ffmpeg > /dev/null 2>&1 || (echo "❌ ffmpeg não encontrado. Instale: brew install ffmpeg (macOS) ou apt install ffmpeg (Ubuntu)" && exit 1)
	python scripts/upload_audios.py

clean:
	docker-compose down -v
	@echo "✅ Containers e volumes removidos"

rebuild:
	docker-compose up -d --build
	@echo "✅ Imagens reconstruídas e containers iniciados"

health:
	curl -s http://localhost:8000/health | jq .

backup-db:
	@mkdir -p backups
	docker exec sales_agent_postgres pg_dump -U $${POSTGRES_USER} $${POSTGRES_DB} > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup realizado em backups/"

migrate:
	docker-compose exec api alembic upgrade head

version:
	docker-compose exec api python -c "import app; print('Sales Agent v1.0.0')"

new-course:
	@if [ -z "$(slug)" ] || [ -z "$(name)" ]; then \
		echo "❌ Uso: make new-course slug=meu_curso name='Nome do Curso' consultant='Nome'"; \
		exit 1; \
	fi
	python scripts/create_course.py --slug "$(slug)" --name "$(name)" --consultant "$(or $(consultant),[Consultor])"

reset-lead:
	@if [ -z "$(phone)" ]; then \
		echo "❌ Uso: make reset-lead phone=5511999999999"; \
		exit 1; \
	fi
	docker compose exec redis redis-cli DEL lead:$(phone) history:$(phone) script_lock:$(phone)
	@echo "✅ Lead $(phone) resetado (sessão, histórico e lock removidos)"
