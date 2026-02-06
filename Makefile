.EXPORT_ALL_VARIABLES:

COMPOSE_FILE ?= docker/docker-compose-local.yml
COMPOSE_PROJECT_NAME ?= eventsourcing_sqlalchemy

POETRY_VERSION=2.2.1
POETRY ?= poetry@$(POETRY_VERSION)

DOTENV_BASE_FILE ?= .env-base
DOTENV_LOCAL_FILE ?= .env

POETRY_INSTALLER_URL ?= https://install.python-poetry.org

-include $(DOTENV_BASE_FILE)
-include $(DOTENV_LOCAL_FILE)

.PHONY: install-poetry
install-poetry:
	@pipx install --suffix="@$(POETRY_VERSION)" "poetry==$(POETRY_VERSION)"
	$(POETRY) --version

.PHONY: poetry-version
poetry-version:
	$(POETRY) --version

.PHONY: python-version
python-version:
	$(POETRY) run python --version

.PHONY: install
install:
	$(POETRY) sync --all-extras $(opts)

.PHONY: update
update: update-lock install

.PHONY: update-lock
update-lock:
	$(POETRY) update --lock -v

.PHONY: docker-up
docker-up:
	docker-compose up -d
	docker-compose ps

.PHONY: docker-down
docker-down:
	docker-compose stop

.PHONY: docker-logs
docker-logs:
	docker-compose logs --follow

.PHONY: docker-ps
docker-ps:
	docker-compose ps

# Todo: Migrations for SQLAlchemy.
#.PHONY: migrate
#migrate:
#	$(POETRY) run django-admin migrate
#
#.PHONY: migrations
#migrations:
#	$(POETRY) run django-admin makemigrations

.PHONY: lint-bandit
lint-bandit:
	$(POETRY) run bandit --ini .bandit --recursive

.PHONY: lint-black
lint-black:
	$(POETRY) run black --check --diff .

.PHONY: lint-flake8
lint-flake8:
	$(POETRY) run flake8

.PHONY: lint-isort
lint-isort:
	$(POETRY) run isort --check-only --diff .

.PHONY: lint-mypy
lint-mypy:
	$(POETRY) run mypy

.PHONY: lint-python
lint-python: lint-black lint-flake8 lint-isort lint-mypy

.PHONY: lint
lint: lint-python

.PHONY: fmt-black
fmt-black:
	$(POETRY) run black .

.PHONY: fmt-isort
fmt-isort:
	$(POETRY) run isort .

.PHONY: fmt
fmt: fmt-black fmt-isort

.PHONY: test
test:
	$(POETRY) run python -m unittest discover . -v

.PHONY: pytest
pytest:
	$(POETRY) run pytest . -v  --durations 10

.PHONY: build
build:
	$(POETRY) build

.PHONY: publish
publish:
	$(POETRY) publish

.PHONY: start-mssql
start-mssql:
	docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=Password1" \
      -p 1433:1433 --name sql2022 --hostname localhost \
      -d \
      mcr.microsoft.com/mssql/server:2022-latest

.PHONY: stop-mssql
stop-mssql:
	docker stop sql2022
	docker rm sql2022

.PHONY: mssql-sqlcmd-help
mssql-sqlcmd-help:
	docker exec -it sql2022 "/opt/mssql-tools18/bin/sqlcmd" \
    -?

.PHONY: mssql-sqlcmd
mssql-sqlcmd:
	docker exec -it sql2022 "/opt/mssql-tools18/bin/sqlcmd" \
    -S localhost -U sa -P Password1 -No

.PHONY: create-mssql-database
create-mssql-database:
	docker exec sql2022 "/opt/mssql-tools18/bin/sqlcmd" \
    -S localhost -U sa -P Password1 -No \
    -q "CREATE DATABASE eventsourcing_sqlalchemy;"

.PHONY: drop-mssql-database
drop-mssql-database:
	docker exec sql2022 "/opt/mssql-tools18/bin/sqlcmd" \
    -S localhost -U sa -P Password1 -No \
    -q "DROP DATABASE eventsourcing_sqlalchemy;"

.PHONY: create-mssql-schema
create-mssql-schema:
	docker exec sql2022 "/opt/mssql-tools18/bin/sqlcmd" \
    -S localhost -U sa -P Password1 -No \
    -d eventsourcing_sqlalchemy \
    -q "CREATE SCHEMA myschema;"

.PHONY: drop-mssql-schema
drop-mssql-schema:
	docker exec sql2022 "/opt/mssql-tools18/bin/sqlcmd" \
    -S localhost -U sa -P Password1 -No \
    -d eventsourcing_sqlalchemy \
    -q "DROP SCHEMA myschema;"

.PHONY: drop-mssql-table
drop-mssql-table:
	docker exec sql2022 "/opt/mssql-tools18/bin/sqlcmd" \
    -S localhost -U sa -P Password1 -No \
    -d eventsourcing_sqlalchemy \
    -q "DROP TABLE $(name);"
