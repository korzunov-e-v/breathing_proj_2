migrations:
	alembic revision --autogenerate

restart:
	docker compose up -d --force-recreate

bot-log:
	docker compose logs bot -f
