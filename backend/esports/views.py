from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .exceptions import Conflict
from .models import Match, Player, Team, Tournament
from .serializers import (
    MatchSerializer, PlayerSerializer, StandingSerializer, TeamRegistrationSerializer,
    TeamSerializer, TournamentSerializer, lock_tournament,
)


def bool_param(request, name):
    """Read ?name=true/false; None when absent, 400 for anything else."""
    value = request.query_params.get(name)
    if value is None:
        return None
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
        return False
    raise ValidationError({name: "Use true or false."})


def int_param(request, name):
    value = request.query_params.get(name)
    if value is None:
        return None
    # isascii() rejects digits like "²" that isdigit() accepts but int() can't parse;
    # the upper bound keeps the value inside PostgreSQL's bigint.
    if not (value.isascii() and value.isdigit()) or int(value) > 2**63 - 1:
        raise ValidationError({name: "Must be a positive integer."})
    return int(value)


def choice_param(request, name, choices):
    value = request.query_params.get(name)
    if value is not None and value not in choices:
        raise ValidationError({name: f"Must be one of: {', '.join(choices)}."})
    return value


class LockOnUpdateMixin:
    """On PUT/PATCH, load the record with a row lock held until the request commits.

    Validation and save then both work on the latest data, so a concurrent update
    can't be overwritten with stale values.
    """

    def get_object(self):
        obj = super().get_object()
        if self.action in ("update", "partial_update"):
            obj = type(obj).objects.select_for_update(no_key=True).get(pk=obj.pk)
        return obj


class TeamViewSet(LockOnUpdateMixin, viewsets.ModelViewSet):
    serializer_class = TeamSerializer

    @extend_schema(parameters=[OpenApiParameter("region", str, enum=Team.Region.values)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        teams = Team.objects.all()
        if self.action == "list":
            region = choice_param(self.request, "region", Team.Region.values)
            if region:
                teams = teams.filter(region=region)
        return teams

    @extend_schema(responses=PlayerSerializer(many=True))
    @action(detail=True)
    def players(self, request, pk=None):
        """Players on this team."""
        team = self.get_object()
        return Response(PlayerSerializer(team.players.all(), many=True).data)

    @extend_schema(responses=MatchSerializer(many=True))
    @action(detail=True)
    def matches(self, request, pk=None):
        """Every match this team plays, in any tournament."""
        team = self.get_object()
        matches = Match.objects.filter(Q(team_a=team) | Q(team_b=team))
        return Response(MatchSerializer(matches, many=True).data)


class PlayerViewSet(LockOnUpdateMixin, viewsets.ModelViewSet):
    serializer_class = PlayerSerializer

    @extend_schema(parameters=[
        OpenApiParameter("team", int, description="Team id."),
        OpenApiParameter("role", str, enum=Player.Role.values),
        OpenApiParameter("country", str, description="2-letter code, e.g. KZ."),
        OpenApiParameter("free_agent", bool, description="true: only players without a team."),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        players = Player.objects.select_related("team")
        if self.action == "list":
            team = int_param(self.request, "team")
            role = choice_param(self.request, "role", Player.Role.values)
            country = self.request.query_params.get("country")
            free_agent = bool_param(self.request, "free_agent")
            if team is not None:
                players = players.filter(team_id=team)
            if role:
                players = players.filter(role=role)
            if country:
                players = players.filter(country=country.upper())
            if free_agent is not None:
                players = players.filter(team__isnull=free_agent)
        return players


class TournamentViewSet(LockOnUpdateMixin, viewsets.ModelViewSet):
    serializer_class = TournamentSerializer

    @extend_schema(parameters=[
        OpenApiParameter("status", str, enum=Tournament.Status.values),
        OpenApiParameter("game", str, description="Exact game name, case-insensitive."),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        tournaments = Tournament.objects.prefetch_related("teams")
        if self.action == "list":
            status_ = choice_param(self.request, "status", Tournament.Status.values)
            game = self.request.query_params.get("game")
            if status_:
                tournaments = tournaments.filter(status=status_)
            if game:
                tournaments = tournaments.filter(game__iexact=game)
        return tournaments

    @extend_schema(methods=["GET"], responses=TeamSerializer(many=True))
    @extend_schema(methods=["POST"], request=TeamRegistrationSerializer, responses={201: TeamSerializer})
    @action(detail=True, methods=["get", "post"])
    def teams(self, request, pk=None):
        """GET: registered teams. POST {"team_id": n}: register a team."""
        tournament = self.get_object()
        if request.method == "GET":
            return Response(TeamSerializer(tournament.teams.all(), many=True).data)

        body = TeamRegistrationSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        team = body.validated_data["team"]
        # Without the lock, two requests could both see a free slot and both register.
        tournament = lock_tournament(tournament.pk)
        if tournament.status == Tournament.Status.FINISHED:
            raise Conflict("Registration is closed: the tournament is finished.")
        if tournament.teams.filter(pk=team.pk).exists():
            raise Conflict(f"{team.name} is already registered.")
        if tournament.teams.count() >= tournament.max_teams:
            raise Conflict(f"The tournament is full ({tournament.max_teams} teams).")
        tournament.teams.add(team)
        return Response(TeamSerializer(team).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"teams/(?P<team_id>\d+)")
    def unregister_team(self, request, pk=None, team_id=None):
        """Remove a team from the tournament, if it has no matches there."""
        tournament = lock_tournament(self.get_object().pk)
        team = get_object_or_404(tournament.teams, pk=team_id)
        if tournament.matches.filter(Q(team_a=team) | Q(team_b=team)).exists():
            raise Conflict(f"{team.name} already has matches in this tournament.")
        tournament.teams.remove(team)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=MatchSerializer(many=True))
    @action(detail=True)
    def matches(self, request, pk=None):
        """Matches in this tournament, in schedule order."""
        tournament = self.get_object()
        return Response(MatchSerializer(tournament.matches.all(), many=True).data)

    @extend_schema(responses=StandingSerializer(many=True))
    @action(detail=True)
    def standings(self, request, pk=None):
        """Table of registered teams from completed matches: 3 points a win, 1 a draw."""
        tournament = self.get_object()
        table = {
            team.id: {"team": team.id, "team_name": team.name, "played": 0, "wins": 0, "draws": 0,
                      "losses": 0, "score_for": 0, "score_against": 0, "points": 0}
            for team in tournament.teams.all()
        }
        for match in tournament.matches.filter(status=Match.Status.COMPLETED):
            for team_id, scored, conceded in ((match.team_a_id, match.score_a, match.score_b),
                                              (match.team_b_id, match.score_b, match.score_a)):
                row = table.get(team_id)
                if row is None:
                    continue
                row["played"] += 1
                row["score_for"] += scored
                row["score_against"] += conceded
                if scored > conceded:
                    row["wins"] += 1
                    row["points"] += 3
                elif scored == conceded:
                    row["draws"] += 1
                    row["points"] += 1
                else:
                    row["losses"] += 1
        rows = sorted(table.values(), key=lambda r: (-r["points"], r["score_against"] - r["score_for"], r["team_name"]))
        return Response(StandingSerializer(rows, many=True).data)


class MatchViewSet(LockOnUpdateMixin, viewsets.ModelViewSet):
    serializer_class = MatchSerializer

    @extend_schema(parameters=[
        OpenApiParameter("tournament", int, description="Tournament id."),
        OpenApiParameter("team", int, description="Matches where this team plays either side."),
        OpenApiParameter("status", str, enum=Match.Status.values),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        matches = Match.objects.all()
        if self.action == "list":
            tournament = int_param(self.request, "tournament")
            team = int_param(self.request, "team")
            status_ = choice_param(self.request, "status", Match.Status.values)
            if tournament is not None:
                matches = matches.filter(tournament_id=tournament)
            if team is not None:
                matches = matches.filter(Q(team_a_id=team) | Q(team_b_id=team))
            if status_:
                matches = matches.filter(status=status_)
        return matches
