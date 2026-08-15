import re
from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class AuthenticationFlowTests(APITestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "StrongPass123!"
        self.user = self.user_model.objects.create_user(
            username="practice@example.com",
            email="practice@example.com",
            first_name="Practice User",
            password=self.password,
        )
        self.user.profile.dob = date(1995, 5, 17)
        self.user.profile.save()

    def test_registration_creates_user_profile_and_logs_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "name": "New User",
                "email": "newuser@example.com",
                "dob": "2000-01-15",
                "password": "AnotherStrongPass123!",
                "confirm_password": "AnotherStrongPass123!",
            },
            format="json",
        )

        created_user = self.user_model.objects.get(email="newuser@example.com")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Registration successful.")
        self.assertEqual(created_user.username, "newuser@example.com")
        self.assertEqual(created_user.first_name, "New User")
        self.assertEqual(str(created_user.profile.dob), "2000-01-15")
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(created_user.pk))

    def test_login_with_email_and_password(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": "practice@example.com",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Login successful.")
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(self.user.pk))

    def test_logout_clears_authenticated_session(self):
        self.client.login(username="practice@example.com", password=self.password)

        response = self.client.post(reverse("logout"), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Logout successful.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_flow_updates_password(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "practice@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r"http://testserver(?P<path>/[^\s]+)", mail.outbox[0].body)
        self.assertIsNotNone(match)

        reset_path = match.group("path")
        complete_response = self.client.post(
            reset_path,
            {
                "new_password": "BrandNewStrongPass123!",
                "confirm_password": "BrandNewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            complete_response.data["message"],
            "Password has been reset successfully.",
        )

        login_response = self.client.post(
            reverse("login"),
            {
                "email": "practice@example.com",
                "password": "BrandNewStrongPass123!",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_home_page_requires_authentication(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(str(response.data["detail"]), "Authentication credentials were not provided.")

    def test_profile_page_requires_authentication(self):
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(str(response.data["detail"]), "Authentication credentials were not provided.")

    def test_profile_page_shows_registered_user_details(self):
        self.client.login(username="practice@example.com", password=self.password)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "name": "Practice User",
                "email": "practice@example.com",
                "dob": "1995-05-17",
            },
        )
