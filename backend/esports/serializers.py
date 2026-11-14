from rest_framework import serializers

from .models import Match, Player, Team, Tournament


def lock_tournament(pk):
    """Re-read a tournament with a row lock held until the request's transaction ends.

    Registration and match writes take this lock, and tournament updates lock the same
    row in the view, so their checks (capacity, registered teams, match dates) run one
    at a time per tournament.
    """
    return Tournament.objects.select_for_update(no_key=True).get(pk=pk)


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "tag", "region", "founded", "created_at"]

    def to_internal_value(self, data):
        # Accept "navi" and store "NAVI".
        if isinstance(data, dict) and isinstance(data.get("tag"), str):
            data = {**data, "tag": data["tag"].strip().upper()}
        return super().to_internal_value(data)


class PlayerSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True, default=None)

    class Meta:
        model = Player
        fields = ["id", "nickname", "real_name", "country", "role", "team", "team_name", "created_at"]

    def to_internal_value(self, data):
        if isinstance(data, dict) and isinstance(data.get("country"), str):
            data = {**data, "country": data["country"].strip().upper()}
        return super().to_internal_value(data)


class TournamentSerializer(serializers.ModelSerializer):
    teams = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Tournament
        fields = ["id", "name", "game", "start_date", "end_date", "prize_pool", "max_teams", "status", "teams"]
        extra_kwargs = {"teams": {"help_text": "Registered team ids. Change with /tournaments/{id}/teams/."}}

    def validate(self, attrs):
        # On PATCH, fall back to the stored values for fields that weren't sent.
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date can't be before the start date."})
        if self.instance is None:
            return attrs

        # The view loaded self.instance with a row lock (LockOnUpdateMixin), so these
        # checks and the save see the latest data, and registrations and matches wait.
        tournament = self.instance
        errors = {}
        registered = tournament.teams.count()
        max_teams = attrs.get("max_teams")
        if max_teams is not None and max_teams < registered:
            errors["max_teams"] = f"{registered} teams are already registered."
        if tournament.matches.filter(scheduled_at__date__lt=start).exists():
            errors["start_date"] = "Some matches are scheduled before this date."
        if tournament.matches.filter(scheduled_at__date__gt=end).exists():
            errors["end_date"] = "Some matches are scheduled after this date."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class TeamRegistrationSerializer(serializers.Serializer):
    team_id = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), source="team")


class MatchSerializer(serializers.ModelSerializer):
    winner = serializers.IntegerField(source="winner_id", read_only=True, allow_null=True,
                                      help_text="Winning team id; null if scheduled or a draw.")

    class Meta:
        model = Match
        fields = ["id", "tournament", "team_a", "team_b", "round", "scheduled_at",
                  "status", "score_a", "score_b", "winner"]

    def validate(self, attrs):
        def current(field):
            return attrs.get(field, getattr(self.instance, field, None))

        tournament, team_a, team_b = current("tournament"), current("team_a"), current("team_b")
        errors = {}
        if team_a and team_b and team_a == team_b:
            errors["team_b"] = "A team can't play against itself."
        if tournament:
            tournament = lock_tournament(tournament.pk)
            registered = set(tournament.teams.values_list("id", flat=True))
            for field, team in (("team_a", team_a), ("team_b", team_b)):
                if team and team.id not in registered:
                    errors[field] = f"{team.name} is not registered in {tournament.name}."
            scheduled_at = current("scheduled_at")
            if scheduled_at and not tournament.start_date <= scheduled_at.date() <= tournament.end_date:
                errors["scheduled_at"] = (
                    f"Must be between {tournament.start_date} and {tournament.end_date}."
                )

        status, score_a, score_b = current("status") or Match.Status.SCHEDULED, current("score_a"), current("score_b")
        if status == Match.Status.COMPLETED and (score_a is None or score_b is None):
            errors["status"] = "A completed match needs score_a and score_b."
        if status == Match.Status.SCHEDULED and (score_a is not None or score_b is not None):
            errors["status"] = "Set status to completed when entering scores."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class StandingSerializer(serializers.Serializer):
    team = serializers.IntegerField()
    team_name = serializers.CharField()
    played = serializers.IntegerField()
    wins = serializers.IntegerField()
    draws = serializers.IntegerField()
    losses = serializers.IntegerField()
    score_for = serializers.IntegerField()
    score_against = serializers.IntegerField()
    points = serializers.IntegerField(help_text="3 per win, 1 per draw.")
