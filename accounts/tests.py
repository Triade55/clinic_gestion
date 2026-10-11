from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_with_email(self):
        user = User.objects.create_user(
            email="soignant@clinique.fr",
            password="TestPassword123!",
            first_name="Jean",
            last_name="Dupont",
            role=User.Role.DOCTOR,
        )
        self.assertEqual(user.email, "soignant@clinique.fr")
        self.assertTrue(user.check_password("TestPassword123!"))
        self.assertEqual(user.role, User.Role.DOCTOR)
        self.assertTrue(user.is_doctor)
        self.assertFalse(user.is_nurse)
        self.assertFalse(user.is_admin_role)

    def test_create_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="TestPassword123!")

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(
            email="directeur@clinique.fr",
            password="AdminPassword123!",
            first_name="Paul",
            last_name="Directeur",
        )
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertEqual(superuser.role, User.Role.ADMIN)
        self.assertTrue(superuser.is_admin_role)


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="dr.martin@clinique.fr",
            password="DoctorPass123!",
            first_name="Alexandre",
            last_name="Martin",
            role=User.Role.DOCTOR,
        )

    def test_login_page_renders_successfully(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Espace Professionnel")
        self.assertContains(response, "Adresse email")

    def test_successful_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "dr.martin@clinique.fr",
                "password": "DoctorPass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bienvenue, Alexandre Martin")
        self.assertTrue(response.context["user"].is_authenticated)

    def test_failed_login_with_wrong_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "dr.martin@clinique.fr",
                "password": "WrongPassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Adresse email ou mot de passe incorrect")

    def test_unauthenticated_dashboard_redirects_to_login(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_logout(self):
        self.client.login(username="dr.martin@clinique.fr", password="DoctorPass123!")
        response = self.client.get(reverse("accounts:logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vous avez été déconnecté avec succès")
