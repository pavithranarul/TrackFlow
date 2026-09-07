"""TrackFlow uses Django's built-in ``auth.User``.

Every foreign key in the project points at ``settings.AUTH_USER_MODEL`` rather
than at ``auth.User`` directly, so a custom user model can still be introduced
later without touching the other apps' code — it would only need a data
migration. No model is defined here.
"""
