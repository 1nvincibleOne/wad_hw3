from datetime import date, datetime, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from esports.models import Match, Player, Team, Tournament

TEAMS = [
    # name, tag, region, founded
    ("Natus Vincere", "NAVI", "CIS", date(2009, 12, 17)),
    ("Team Spirit", "SPIRIT", "CIS", date(2015, 12, 1)),
    ("FaZe Clan", "FAZE", "EU", date(2010, 5, 30)),
    ("Team Liquid", "LIQUID", "NA", date(2000, 1, 1)),
    ("Steppe Wolves", "STW", "CIS", date(2021, 3, 14)),
    ("Nomad Esports", "NMD", "CIS", date(2023, 9, 1)),
]

PLAYERS = [
    # nickname, real name, country, role, team tag (None = free agent)
    ("Aleksib", "Aleksi Virolainen", "FI", "captain", "NAVI"),
    ("iM", "Ivan Mihai", "RO", "core", "NAVI"),
    ("w0nderful", "Ihor Zhdanov", "UA", "core", "NAVI"),
    ("chopper", "Leonid Vishnyakov", "RU", "captain", "SPIRIT"),
    ("donk", "Danil Kryshkovets", "RU", "core", "SPIRIT"),
    ("zont1x", "Myroslav Plakhotja", "UA", "support", "SPIRIT"),
    ("karrigan", "Finn Andersen", "DK", "captain", "FAZE"),
    ("rain", "Havard Nygaard", "NO", "core", "FAZE"),
    ("broky", "Helvijs Saukants", "LV", "core", "FAZE"),
    ("NAF", "Keith Markovic", "CA", "captain", "LIQUID"),
    ("Twistzz", "Russel Van Dulken", "CA", "core", "LIQUID"),
    ("ultimate", "Roland Tomkowiak", "PL", "support", "LIQUID"),
    ("Kaiser", "Arman Seitkali", "KZ", "captain", "STW"),
    ("Burkit", "Daniyar Omarov", "KZ", "core", "STW"),
    ("Saryarka", "Timur Abenov", "KZ", "substitute", "STW"),
    ("Altyn", "Aibek Nurlanov", "KZ", "captain", "NMD"),
    ("Kokpar", "Erlan Zhakupov", "KZ", "core", "NMD"),
    ("Tumar", "Aruzhan Bekova", "KZ", "support", None),
]


def at(day, hour):
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


class Command(BaseCommand):
    help = "Add demo teams, players, tournaments and matches if the database has no teams."

    @transaction.atomic
    def handle(self, *args, **options):
        if Team.objects.exists():
            self.stdout.write("Teams already exist; skipping seed.")
            return

        teams = {tag: Team.objects.create(name=name, tag=tag, region=region, founded=founded)
                 for name, tag, region, founded in TEAMS}
        for nickname, real_name, country, role, tag in PLAYERS:
            Player.objects.create(nickname=nickname, real_name=real_name, country=country, role=role,
                                  team=teams.get(tag))

        major = Tournament.objects.create(
            name="Almaty Major 2026", game="Counter-Strike 2", start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5), prize_pool=250000, max_teams=8, status="finished",
        )
        major.teams.set([teams[t] for t in ("NAVI", "SPIRIT", "FAZE", "STW")])
        day = major.start_date
        for round_, (a, b, score_a, score_b) in enumerate([
            ("NAVI", "SPIRIT", 2, 1), ("FAZE", "STW", 2, 0),
            ("NAVI", "FAZE", 1, 1), ("SPIRIT", "STW", 2, 1),
            ("NAVI", "STW", 2, 0), ("SPIRIT", "FAZE", 0, 2),
        ]):
            Match.objects.create(
                tournament=major, team_a=teams[a], team_b=teams[b], round=round_ // 2 + 1,
                scheduled_at=at(day, 12 + 3 * (round_ % 2)), status="completed", score_a=score_a, score_b=score_b,
            )

        cup = Tournament.objects.create(
            name="Astana Cup 2026", game="Counter-Strike 2", start_date=date(2026, 12, 10),
            end_date=date(2026, 12, 14), prize_pool=100000, max_teams=8,
        )
        cup.teams.set([teams[t] for t in ("NAVI", "LIQUID", "NMD", "FAZE")])
        Match.objects.create(tournament=cup, team_a=teams["NAVI"], team_b=teams["NMD"], round=1,
                             scheduled_at=at(cup.start_date, 14))
        Match.objects.create(tournament=cup, team_a=teams["LIQUID"], team_b=teams["FAZE"], round=1,
                             scheduled_at=at(cup.start_date, 17))

        Tournament.objects.create(
            name="Steppe Invitational 2027", game="Dota 2", start_date=date(2027, 2, 1),
            end_date=date(2027, 2, 3), prize_pool=50000, max_teams=4,
        )
        self.stdout.write(self.style.SUCCESS("Seeded 6 teams, 18 players, 3 tournaments, 8 matches."))
