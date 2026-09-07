from django.contrib.auth import get_user_model

User = get_user_model()


def get_users():
    return User.objects.filter(is_active=True).order_by("username")


def get_user(user_id):
    return User.objects.filter(id=user_id, is_active=True).first()
