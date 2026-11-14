# Esports Tournaments API

A REST API for running esports tournaments, built with Django REST Framework and PostgreSQL. It manages teams and their players, tournament registration, match results and standings.

- Teams register for tournaments, up to each tournament's `max_teams` limit.
- Matches are checked against the tournament: both teams must be registered, and the date must fall within the tournament's dates.
- Standings are calculated from completed matches: 3 points for a win, 1 for a draw.
- Teams with match history can't be deleted.

## Running locally

Requires Docker with Compose v2.

1. Copy [`.env.example`](.env.example) to `.env` and set `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY`.
2. Run `docker compose up --build`.
3. Open http://localhost:8000/api/docs/ for Swagger UI.

On start, the backend applies migrations and, with `SEED_DEMO_DATA=true`, adds demo data to an empty database: 6 teams, 18 players, 3 tournaments and 8 matches. To use the Django admin at `/admin/`, first create a user:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Data model

| Model | Key fields | Relationships |
| --- | --- | --- |
| Team | name, tag, region, founded | has many Players and Matches; plays in many Tournaments |
| Player | nickname, country, role | belongs to one Team (optional) |
| Tournament | name, game, dates, prize_pool, max_teams, status | has many Matches; has many Teams (many-to-many) |
| Match | round, scheduled_at, status, score_a, score_b | belongs to one Tournament and two Teams |

## Documentation and testing

- Endpoint reference: [docs/API.md](docs/API.md). It lists all 31 endpoints with their parameters, request bodies and responses.
- Postman collection: [postman/esports.postman_collection.json](postman/esports.postman_collection.json). Import it and choose Run collection. It goes through the app's lifecycle in order, from creating teams to cleanup, so later requests reuse ids saved by earlier ones. If you change `APP_PORT`, update its `baseUrl` variable.
