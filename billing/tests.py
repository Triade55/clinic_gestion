from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from billing.forms import EncaissementForm
from billing.models import Invoice, Patient, Specialty

User = get_user_model()


class BillingModelTests(TestCase):
    def setUp(self):
        self.specialty = Specialty.objects.create(name="Médecine Générale", price=5000)
        self.secretary = User.objects.create_user(
            email="sec.test@clinique.fr",
            password="SecretaryPass123!",
            role=User.Role.SECRETARY,
        )

    def test_generate_patient_number(self):
        num1 = Patient.generate_patient_number()
        p1 = Patient.objects.create(
            patient_number=num1,
            first_name="Jean",
            last_name="Kouamé",
        )
        self.assertTrue(num1.startswith("PAT-"))

        num2 = Patient.generate_patient_number()
        self.assertNotEqual(num1, num2)
        p2 = Patient.objects.create(
            patient_number=num2,
            first_name="Awa",
            last_name="Touré",
        )
        self.assertEqual(int(num2.split("-")[-1]), int(num1.split("-")[-1]) + 1)

    def test_invoice_creation_and_change_calculation(self):
        patient = Patient.objects.create(
            patient_number="PAT-2026-0099",
            first_name="Seydou",
            last_name="Bamba",
        )
        invoice = Invoice.objects.create(
            patient=patient,
            specialty=self.specialty,
            consultation_fee=self.specialty.price,
            amount_received=10000,
            created_by=self.secretary,
        )
        # 10 000 reçu - 5 000 tarif = 5 000 rendu
        self.assertEqual(invoice.amount_change, 5000)
        self.assertTrue(invoice.invoice_number.startswith("FAC-"))

    def test_invoice_partial_payment(self):
        patient = Patient.objects.create(
            patient_number="PAT-2026-0100",
            first_name="Mamadou",
            last_name="Soro",
        )
        invoice = Invoice.objects.create(
            patient=patient,
            specialty=self.specialty,
            consultation_fee=5000,
            amount_received=3000,  # Moins que le tarif -> Acompte / Partiel
            created_by=self.secretary,
        )
        self.assertEqual(invoice.amount_change, 0)
        self.assertEqual(invoice.amount_remaining, 2000)
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PARTIAL)

    def test_invoice_negative_amount_raises_error(self):
        patient = Patient.objects.create(
            patient_number="PAT-2026-0101",
            first_name="Ali",
            last_name="Touré",
        )
        invoice = Invoice(
            patient=patient,
            specialty=self.specialty,
            consultation_fee=5000,
            amount_received=-100,
            created_by=self.secretary,
        )
        with self.assertRaises(ValidationError):
            invoice.clean()


class EncaissementViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.secretary = User.objects.create_user(
            email="sec.caisse@clinique.fr",
            password="SecPass123!",
            first_name="Julie",
            last_name="Moreau",
            role=User.Role.SECRETARY,
        )
        self.client.login(username="sec.caisse@clinique.fr", password="SecPass123!")
        self.specialty = Specialty.objects.create(name="Pédiatrie", price=7500)

    def test_encaissement_page_get(self):
        response = self.client.get(reverse("billing:encaissement"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accueil & Encaissement Consultation")
        self.assertContains(response, "Pédiatrie")

    def test_new_patient_encaissement_post(self):
        response = self.client.post(
            reverse("billing:encaissement"),
            {
                "patient_mode": "NEW",
                "first_name": "Ibrahim",
                "last_name": "Cissé",
                "phone_number": "07 11 22 33 44",
                "specialty": self.specialty.pk,
                "amount_received": 10000,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        # Le patient doit être créé avec son numéro unique
        patient = Patient.objects.get(first_name="Ibrahim", last_name="Cissé")
        self.assertTrue(patient.patient_number.startswith("PAT-"))

        # La facture doit être créée avec la monnaie rendue
        invoice = Invoice.objects.get(patient=patient)
        self.assertEqual(invoice.consultation_fee, 7500)
        self.assertEqual(invoice.amount_received, 10000)
        self.assertEqual(invoice.amount_change, 2500)

        # La page de facture imprimable est affichée
        self.assertContains(response, patient.patient_number)
        self.assertContains(response, "MONNAIE RENDUE")
        self.assertContains(response, "2 500 FCFA")

    def test_existing_patient_encaissement_post(self):
        existing_patient = Patient.objects.create(
            patient_number="PAT-2026-0005",
            first_name="Amina",
            last_name="Bakayoko",
            phone_number="01 02 03 04 05",
        )

        response = self.client.post(
            reverse("billing:encaissement"),
            {
                "patient_mode": "EXISTING",
                "existing_patient_number": "PAT-2026-0005",
                "specialty": self.specialty.pk,
                "amount_received": 7500,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        invoice = Invoice.objects.filter(patient=existing_patient).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.amount_change, 0)
        self.assertContains(response, "PAT-2026-0005")

    def test_partial_payment_encaissement_post(self):
        response = self.client.post(
            reverse("billing:encaissement"),
            {
                "patient_mode": "NEW",
                "first_name": "Salif",
                "last_name": "Keita",
                "phone_number": "07 99 88 77 66",
                "specialty": self.specialty.pk,
                "amount_received": 5000,  # Moins que le tarif de 7500
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        patient = Patient.objects.get(first_name="Salif", last_name="Keita")
        invoice = Invoice.objects.get(patient=patient)
        self.assertEqual(invoice.amount_received, 5000)
        self.assertEqual(invoice.amount_change, 0)
        self.assertEqual(invoice.amount_remaining, 2500)
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PARTIAL)
        self.assertContains(response, "RESTE À PAYER")
        self.assertContains(response, "2 500 FCFA")

    def test_invoice_list_view(self):
        response = self.client.get(reverse("billing:invoice_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Historique des Factures")

    def test_patient_search_by_query(self):
        p1 = Patient.objects.create(
            patient_number="PAT-2026-0888",
            first_name="Kadiatou",
            last_name="Sanogo",
            phone_number="07 08 09 10 11",
        )
        # Création d'une consultation passée
        Invoice.objects.create(
            patient=p1,
            specialty=self.specialty,
            consultation_fee=7500,
            amount_received=7500,
            created_by=self.secretary,
        )

        # Recherche par IPP
        res = self.client.get(reverse("billing:patient_search"), {"q": "0888"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["patient_number"], "PAT-2026-0888")
        self.assertEqual(data["results"][0]["invoices_count"], 1)

        # Recherche par nom de famille
        res_name = self.client.get(reverse("billing:patient_search"), {"q": "Sanogo"})
        self.assertEqual(res_name.status_code, 200)
        data_name = res_name.json()
        self.assertEqual(len(data_name["results"]), 1)
        self.assertEqual(data_name["results"][0]["first_name"], "Kadiatou")

        # Recherche par téléphone
        res_phone = self.client.get(reverse("billing:patient_search"), {"q": "09 10"})
        self.assertEqual(res_phone.status_code, 200)
        data_phone = res_phone.json()
        self.assertEqual(len(data_phone["results"]), 1)

    def test_patient_search_by_exact_number(self):
        Patient.objects.create(
            patient_number="PAT-2026-0999",
            first_name="Oumar",
            last_name="Koné",
            phone_number="01 02 03 04 05",
        )
        res = self.client.get(reverse("billing:patient_search"), {"patient_number": "PAT-2026-0999"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["patient_number"], "PAT-2026-0999")

    def test_patient_search_unauthenticated(self):
        self.client.logout()
        res = self.client.get(reverse("billing:patient_search"), {"q": "test"})
        self.assertEqual(res.status_code, 302)

