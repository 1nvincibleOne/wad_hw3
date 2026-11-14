# Esports Tournaments API reference

Base URL: `http://localhost:8000/api` (the host port is `APP_PORT` in `.env`). Interactive docs: `/api/docs/` (Swagger UI) and `/api/redoc/`; OpenAPI schema at `/api/schema/`.

- Bodies are JSON. Every URL ends with `/`.
- Lists are not paginated.
- `PUT` must include every required field; optional fields left out keep their current values. `PATCH` changes only the fields sent.
- Read-only fields (`id`, `created_at`, `team_name`, `winner`, a tournament's `teams`) are ignored in request bodies.

## Status codes

| Code | When | Body |
| --- | --- | --- |
| 200 | Read or update succeeded | The resource |
| 201 | Created | The new resource |
| 204 | Deleted | Empty |
| 400 | Invalid body or query parameter | Field errors: `{"tag": ["Tag must be 2-6 uppercase letters or digits."]}` |
| 404 | Unknown id | `{"detail": "No Team matches the given query."}` |
| 409 | The change conflicts with existing data | `{"detail": "..."}` |

## Teams

| Field | Type | Rules |
| --- | --- | --- |
| `id` | integer | Read-only |
| `name` | string | Required, unique, max 100 |
| `tag` | string | Required, unique, 2–6 letters or digits, stored uppercase |
| `region` | string | Required: `EU`, `CIS`, `NA`, `SA`, `ASIA`, `OCE` |
| `founded` | date | Optional, `YYYY-MM-DD` |
| `created_at` | datetime | Read-only |

| Method | URL | Parameters / body | Response |
| --- | --- | --- | --- |
| GET | `/teams/` | Query: `region` | 200, list of teams by name |
| POST | `/teams/` | `{"name": "Steppe Wolves", "tag": "STW", "region": "CIS", "founded": "2021-03-14"}` | 201, team; 400 |
| GET | `/teams/{id}/` | | 200, team; 404 |
| PUT | `/teams/{id}/` | All fields: `name`, `tag`, `region`, optional `founded` | 200; 400; 404 |
| PATCH | `/teams/{id}/` | Any subset, e.g. `{"region": "EU"}` | 200; 400; 404 |
| DELETE | `/teams/{id}/` | | 204; 404; 409 if the team has matches. Its players become free agents. |
| GET | `/teams/{id}/players/` | | 200, players on the team; 404 |
| GET | `/teams/{id}/matches/` | | 200, the team's matches in every tournament; 404 |

## Players

| Field | Type | Rules |
| --- | --- | --- |
| `id` | integer | Read-only |
| `nickname` | string | Required, unique, max 32 |
| `real_name` | string | Optional, max 100 |
| `country` | string | Required, 2-letter code, stored uppercase |
| `role` | string | `captain`, `core` (default), `support`, `substitute` |
| `team` | integer or null | Team id; null for a free agent |
| `team_name` | string or null | Read-only |
| `created_at` | datetime | Read-only |

| Method | URL | Parameters / body | Response |
| --- | --- | --- | --- |
| GET | `/players/` | Query: `team` (id), `role`, `country`, `free_agent` (`true`/`false`) | 200, list by nickname; 400 for a bad filter value |
| POST | `/players/` | `{"nickname": "Kaiser", "real_name": "Arman Seitkali", "country": "KZ", "role": "captain", "team": 5}` | 201; 400 (also for an unknown team id) |
| GET | `/players/{id}/` | | 200; 404 |
| PUT | `/players/{id}/` | All fields: `nickname`, `country`, optional `real_name`, `role`, `team` | 200; 400; 404 |
| PATCH | `/players/{id}/` | Any subset, e.g. `{"team": null}` to release a player | 200; 400; 404 |
| DELETE | `/players/{id}/` | | 204; 404 |

## Tournaments

| Field | Type | Rules |
| --- | --- | --- |
| `id` | integer | Read-only |
| `name` | string | Required, unique, max 150 |
| `game` | string | Required, max 50 |
| `start_date`, `end_date` | date | Required; `end_date` can't be before `start_date`; on update, the range must still include every scheduled match |
| `prize_pool` | decimal string | ≥ 0, default `"0.00"` |
| `max_teams` | integer | 2–64, default 8; can't go below the number already registered |
| `status` | string | `upcoming` (default), `ongoing`, `finished` |
| `teams` | list of integers | Read-only; change with the registration endpoints |

| Method | URL | Parameters / body | Response |
| --- | --- | --- | --- |
| GET | `/tournaments/` | Query: `status`, `game` (exact, case-insensitive) | 200, list by start date |
| POST | `/tournaments/` | `{"name": "Astana Cup 2026", "game": "Counter-Strike 2", "start_date": "2026-12-10", "end_date": "2026-12-14", "prize_pool": "100000.00", "max_teams": 8}` | 201; 400 |
| GET | `/tournaments/{id}/` | | 200; 404 |
| PUT | `/tournaments/{id}/` | All fields except `teams` | 200; 400; 404 |
| PATCH | `/tournaments/{id}/` | Any subset, e.g. `{"status": "ongoing"}` | 200; 400; 404 |
| DELETE | `/tournaments/{id}/` | Also deletes its matches | 204; 404 |
| GET | `/tournaments/{id}/teams/` | | 200, registered teams; 404 |
| POST | `/tournaments/{id}/teams/` | `{"team_id": 3}` | 201, the team; 400 for an unknown team; 404; 409 if already registered, the tournament is full, or it is finished |
| DELETE | `/tournaments/{id}/teams/{team_id}/` | | 204; 404 if the team isn't registered; 409 if it has matches in this tournament |
| GET | `/tournaments/{id}/matches/` | | 200, matches in schedule order; 404 |
| GET | `/tournaments/{id}/standings/` | | 200, one row per registered team; 404 |

Standings rows: `team`, `team_name`, `played`, `wins`, `draws`, `losses`, `score_for`, `score_against`, `points`. Only completed matches count: 3 points for a win, 1 for a draw. Rows are sorted by points, then score difference, then name.

## Matches

| Field | Type | Rules |
| --- | --- | --- |
| `id` | integer | Read-only |
| `tournament` | integer | Required tournament id |
| `team_a`, `team_b` | integer | Required team ids; different teams, both registered in the tournament |
| `round` | integer | ≥ 1, default 1 |
| `scheduled_at` | datetime | Required, ISO 8601; its date must fall within the tournament's dates |
| `status` | string | `scheduled` (default) or `completed` |
| `score_a`, `score_b` | integer or null | Null while scheduled; both required once completed |
| `winner` | integer or null | Read-only: winning team id, null if scheduled or a draw |

| Method | URL | Parameters / body | Response |
| --- | --- | --- | --- |
| GET | `/matches/` | Query: `tournament` (id), `team` (id, either side), `status` | 200, list by time; 400 for a bad filter value |
| POST | `/matches/` | `{"tournament": 2, "team_a": 1, "team_b": 6, "round": 1, "scheduled_at": "2026-12-10T14:00:00Z"}` | 201; 400 |
| GET | `/matches/{id}/` | | 200; 404 |
| PUT | `/matches/{id}/` | All fields | 200; 400; 404 |
| PATCH | `/matches/{id}/` | Record a result: `{"status": "completed", "score_a": 2, "score_b": 1}` | 200; 400; 404 |
| DELETE | `/matches/{id}/` | | 204; 404 |
