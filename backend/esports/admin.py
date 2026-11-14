from django.contrib import admin

from .models import Match, Player, Team, Tournament


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "tag", "region", "founded"]
    list_filter = ["region"]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["nickname", "real_name", "country", "role", "team"]
    list_filter = ["role", "team"]


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ["name", "game", "start_date", "end_date", "status", "max_teams"]
    filter_horizontal = ["teams"]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ["tournament", "team_a", "team_b", "round", "scheduled_at", "status", "score_a", "score_b"]
    list_filter = ["tournament", "status"]
