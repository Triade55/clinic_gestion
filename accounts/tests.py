from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from billing.models import Invoice, Patient, Specialty

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

    def test_secretary_dashboard_statistics(self):
        sec = User.objects.create_user(
            email="sec.kpi@clinique.fr",
            password="SecPassword123!",
            role=User.Role.SECRETARY,
        )
        spec = Specialty.objects.create(name="Cardiologie", price=10000)

        p1 = Patient.objects.create(
            patient_number="PAT-2026-9001",
            first_name="Seydou",
            last_name="Touré",
            phone_number="0701020304",
        )
        p2 = Patient.objects.create(
            patient_number="PAT-2026-9002",
            first_name="Fatou",
            last_name="Diop",
            phone_number="0705060708",
        )

        # Facture 1 : Soldée (10 000 payés sur 10 000)
        Invoice.objects.create(
            patient=p1,
            specialty=spec,
            consultation_fee=10000,
            amount_received=10000,
            created_by=sec,
        )

        # Facture 2 : Partiellement réglée (4 000 payés sur 10 000 -> reste 6 000)
        Invoice.objects.create(
            patient=p2,
            specialty=spec,
            consultation_fee=10000,
            amount_received=4000,
            created_by=sec,
        )

        self.client.login(username="sec.kpi@clinique.fr", password="SecPassword123!")
        res = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(res.status_code, 200)

        # Vérifications des variables contextuelles
        self.assertEqual(res.context["today_collected"], 14000)
        self.assertEqual(res.context["today_patients_count"], 2)
        self.assertEqual(res.context["total_unpaid_remaining"], 6000)
        self.assertEqual(res.context["unpaid_invoices_count"], 1)

        # Vérification du contenu HTML
        self.assertContains(res, "Montant Encaissé Aujourd'hui")
        self.assertContains(res, "Patients Enregistrés Aujourd'hui")
        self.assertContains(res, "Factures Non Soldées")
        self.assertContains(res, "14000")
        self.assertContains(res, "6000")
        self.assertContains(res, "DIOP Fatou")

        # Test de mise à jour du tableau de bord suite à un versement ultérieur de 2 000 FCFA
        inv2 = Invoice.objects.get(patient=p2)
        inv2.add_payment(amount_paid=2000, created_by=sec)

        res2 = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(res2.context["today_collected"], 16000)
        self.assertEqual(res2.context["total_unpaid_remaining"], 4000)
        self.assertContains(res2, "16000")
        self.assertContains(res2, "4000")


