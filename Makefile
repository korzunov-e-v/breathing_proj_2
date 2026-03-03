migrations:
	alembic revision --autogenerate

restart:
	docker compose up -d --force-recreate

logs:
	docker compose logs bot -f
