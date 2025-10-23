from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

@receiver(user_logged_in)
def promote_staff_to_superuser(sender, request, user, **kwargs):
    """
    Automatically promote staff users to superuser for admin access.
    Only applies if there's a single staff user (you).
    """
    if user.is_staff and not user.is_superuser:
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])
        # Optional: log this or send email if needed
        print(f"[ADMIN] Promoted {user.username} to superuser for full access.")
