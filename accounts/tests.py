"""Tests for registration, JWT login and the profile endpoints."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
ME_URL = "/api/auth/me/"
PASSWORD_URL = "/api/auth/change-password/"


class RegisterTests(APITestCase):
    def test_register_creates_user_and_returns_tokens(self):
        response = self.client.post(
            REGISTER_URL,
            {
                "username": "newbie",
                "email": "newbie@example.com",
                "password": "s3cure-passw0rd!",
                "password_confirm": "s3cure-passw0rd!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], "newbie")
        self.assertTrue(User.objects.filter(username="newbie").exists())

    def test_register_hashes_the_password(self):
        self.client.post(
            REGISTER_URL,
            {
                "username": "hashed",
                "password": "s3cure-passw0rd!",
                "password_confirm": "s3cure-passw0rd!",
            },
            format="json",
        )

        user = User.objects.get(username="hashed")
        self.assertNotEqual(user.password, "s3cure-passw0rd!")
        self.assertTrue(user.check_password("s3cure-passw0rd!"))

    def test_register_never_returns_the_password(self):
        response = self.client.post(
            REGISTER_URL,
            {
                "username": "quiet",
                "password": "s3cure-passw0rd!",
                "password_confirm": "s3cure-passw0rd!",
            },
            format="json",
        )
        self.assertNotIn("password", response.data["user"])

    def test_register_rejects_mismatched_passwords(self):
        response = self.client.post(
            REGISTER_URL,
            {
                "username": "mismatch",
                "password": "s3cure-passw0rd!",
                "password_confirm": "something-else!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            REGISTER_URL,
            {"username": "weak", "password": "1234", "password_confirm": "1234"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="weak").exists())

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user(username="taken", password="s3cure-passw0rd!")
        response = self.client.post(
            REGISTER_URL,
            {
                "username": "taken",
                "password": "s3cure-passw0rd!",
                "password_confirm": "s3cure-passw0rd!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class JWTFlowTests(APITestCase):
    """The full token lifecycle, exercised over HTTP rather than with
    force_authenticate, so the auth header path is actually covered."""

    def setUp(self):
        self.password = "s3cure-passw0rd!"
        self.user = User.objects.create_user(username="jwtuser", password=self.password)

    def _login(self):
        return self.client.post(
            LOGIN_URL,
            {"username": "jwtuser", "password": self.password},
            format="json",
        )

    def test_login_returns_token_pair(self):
        response = self._login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_is_401(self):
        response = self.client.post(
            LOGIN_URL,
            {"username": "jwtuser", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_authenticates_a_request(self):
        access = self._login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "jwtuser")

    def test_garbage_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_a_new_access_token(self):
        refresh = self._login().data["refresh"]
        response = self.client.post(REFRESH_URL, {"refresh": refresh}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_protected_endpoint_without_a_token_is_401(self):
        self.assertEqual(
            self.client.get(ME_URL).status_code, status.HTTP_401_UNAUTHORIZED
        )


class MeEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profile", password="s3cure-passw0rd!", email="a@example.com"
        )
        self.client.force_authenticate(user=self.user)

    def test_get_me_returns_own_profile(self):
        response = self.client.get(ME_URL)
        self.assertEqual(response.data["username"], "profile")
        self.assertNotIn("password", response.data)

    def test_patch_me_updates_profile_fields(self):
        response = self.client.patch(
            ME_URL, {"first_name": "Pat", "email": "new@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Pat")
        self.assertEqual(self.user.email, "new@example.com")

    def test_patch_me_cannot_change_username(self):
        response = self.client.patch(ME_URL, {"username": "hacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "profile")

    def test_patch_me_cannot_grant_staff(self):
        self.client.patch(ME_URL, {"is_staff": True}, format="json")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)


class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.old = "s3cure-passw0rd!"
        self.user = User.objects.create_user(username="pwuser", password=self.old)
        self.client.force_authenticate(user=self.user)

    def test_change_password_succeeds(self):
        response = self.client.post(
            PASSWORD_URL,
            {"current_password": self.old, "new_password": "an0ther-Str0ng-pw!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("an0ther-Str0ng-pw!"))

    def test_wrong_current_password_is_rejected(self):
        response = self.client.post(
            PASSWORD_URL,
            {"current_password": "not-it", "new_password": "an0ther-Str0ng-pw!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old))

    def test_weak_new_password_is_rejected(self):
        response = self.client.post(
            PASSWORD_URL,
            {"current_password": self.old, "new_password": "1234"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserDirectoryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="s3cure-passw0rd!")
        User.objects.create_user(username="bob", password="s3cure-passw0rd!")
        User.objects.create_user(
            username="ghost", password="s3cure-passw0rd!", is_active=False
        )
        self.client.force_authenticate(user=self.user)

    def test_directory_lists_active_users_only(self):
        response = self.client.get("/api/auth/users/")
        usernames = {u["username"] for u in response.data["results"]}
        self.assertEqual(usernames, {"alice", "bob"})

    def test_directory_is_searchable(self):
        response = self.client.get("/api/auth/users/?search=bo")
        usernames = {u["username"] for u in response.data["results"]}
        self.assertEqual(usernames, {"bob"})

    def test_directory_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get("/api/auth/users/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class SuperuserFlagTests(APITestCase):
    """The UI reads is_superuser to decide what to offer; it must be accurate
    and it must stay read-only."""

    def setUp(self):
        self.plain = User.objects.create_user(username="plain", password="pw-12345678!")
        self.root = User.objects.create_superuser(username="root", password="pw-12345678!")

    def test_me_reports_the_flag(self):
        self.client.force_authenticate(user=self.root)
        self.assertTrue(self.client.get(ME_URL).data["is_superuser"])

        self.client.force_authenticate(user=self.plain)
        self.assertFalse(self.client.get(ME_URL).data["is_superuser"])

    def test_flag_cannot_be_self_granted(self):
        self.client.force_authenticate(user=self.plain)
        self.client.patch(ME_URL, {"is_superuser": True}, format="json")

        self.plain.refresh_from_db()
        self.assertFalse(self.plain.is_superuser)
