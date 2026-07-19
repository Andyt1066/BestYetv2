from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.accounts import pseudonyms

    Profile.objects.create(
        user=instance,
        display_name=instance.username,
        pseudonym=pseudonyms.generate_unique(
            lambda candidate: Profile.objects.filter(pseudonym=candidate).exists()
        ),
    )
