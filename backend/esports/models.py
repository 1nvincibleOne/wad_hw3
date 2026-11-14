from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q


class Team(models.Model):
    class Region(models.TextChoices):
        EUROPE = "EU", "Europe"
        CIS = "CIS", "CIS"
        NORTH_AMERICA = "NA", "North America"
        SOUTH_AMERICA = "SA", "South America"
        ASIA = "ASIA", "Asia"
        OCEANIA = "OCE", "Oceania"

    name = models.CharField(max_length=100, unique=True)
    tag = models.CharField(
        max_length=6, unique=True,
        validators=[RegexValidator(r"^[A-Z0-9]{2,6}$", "Tag must be 2-6 uppercase letters or digits.")],
    )
    region = models.CharField(max_length=4, choices=Region.choices)
    founded = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.tag}]"


class Player(models.Model):
    class Role(models.TextChoices):
        CAPTAIN = "captain", "Captain"
        CORE = "core", "Core"
        SUPPORT = "support", "Support"
        SUBSTITUTE = "substitute", "Substitute"

    # One-to-many: a team has many players. Players without a team are free agents.
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="players")
    nickname = models.CharField(max_length=32, unique=True)
    real_name = models.CharField(max_length=100, blank=True)
    country = models.CharField(
        max_length=2, validators=[RegexValidator(r"^[A-Z]{2}$", "Use a 2-letter country code, e.g. KZ.")],
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CORE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nickname"]

    def __str__(self):
        return self.nickname


class Tournament(models.Model):
    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ONGOING = "ongoing", "Ongoing"
        FINISHED = "finished", "Finished"

    name = models.CharField(max_length=150, unique=True)
    game = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    prize_pool = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    max_teams = models.PositiveSmallIntegerField(default=8, validators=[MinValueValidator(2), MaxValueValidator(64)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UPCOMING)
    # Many-to-many: a tournament has many teams, and a team plays in many tournaments.
    teams = models.ManyToManyField(Team, related_name="tournaments", blank=True)

    class Meta:
        ordering = ["start_date", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="tournament_dates_in_order"),
        ]

    def __str__(self):
        return self.name


class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"

    # One-to-many: a tournament has many matches.
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="matches")
    # PROTECT: a team that has played can't be deleted, so match history stays intact.
    team_a = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="matches_as_a")
    team_b = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="matches_as_b")
    round = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    score_a = models.PositiveSmallIntegerField(null=True, blank=True)
    score_b = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["scheduled_at", "id"]
        verbose_name_plural = "matches"
        constraints = [
            models.CheckConstraint(condition=~Q(team_a=F("team_b")), name="match_teams_differ"),
            models.CheckConstraint(
                condition=(
                    Q(status="scheduled", score_a__isnull=True, score_b__isnull=True)
                    | Q(status="completed", score_a__isnull=False, score_b__isnull=False)
                ),
                name="match_scores_follow_status",
            ),
        ]

    def __str__(self):
        return f"{self.team_a.tag} vs {self.team_b.tag} ({self.tournament})"

    @property
    def winner_id(self):
        if self.status != self.Status.COMPLETED or self.score_a == self.score_b:
            return None
        return self.team_a_id if self.score_a > self.score_b else self.team_b_id
