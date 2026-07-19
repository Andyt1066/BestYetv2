from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    readonly_fields = ("pseudonym", "created_at", "updated_at")

    def has_add_permission(self, request, obj=None):
        return False  # profiles are created by signal, one per user


class UserAdmin(DjangoUserAdmin):
    inlines = (ProfileInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
