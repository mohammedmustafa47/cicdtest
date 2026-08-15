from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "dob")
    search_fields = ("user__email", "user__username", "user__first_name")
