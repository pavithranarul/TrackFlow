from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


@transaction.atomic
def register_user(*, username, password, email="", first_name="", last_name=""):
    """Create a user with a properly hashed password.

    Uses ``create_user`` rather than ``objects.create`` so the password is run
    through the hasher instead of being stored verbatim.
    """
    return User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )


@transaction.atomic
def update_user(*, user, validated_data):
    for field, value in validated_data.items():
        setattr(user, field, value)

    user.save()

    return user


@transaction.atomic
def change_password(*, user, new_password):
    user.set_password(new_password)
    user.save(update_fields=["password"])

    return user
