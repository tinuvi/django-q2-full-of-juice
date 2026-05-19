COMPOSE := docker compose -f test-services-docker-compose.yaml

dev:
	docker compose -f web-docker-compose.yaml up

test:
	$(COMPOSE) run --rm --remove-orphans integration-tests

format:
	$(COMPOSE) run --rm --remove-orphans lint-formatter

shell:
	$(COMPOSE) run --rm integration-tests python manage.py shell

makemigrations:
	$(COMPOSE) run --rm integration-tests python manage.py makemigrations

migrate:
	$(COMPOSE) run --rm integration-tests python manage.py migrate

createsuperuser:
	docker compose -f web-docker-compose.yaml run --rm web python manage.py createsuperuser
