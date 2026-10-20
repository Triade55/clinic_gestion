import datetime
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from billing.models import Invoice, Patient, Specialty
from .models import Appointment, DoctorAvailability

User = get_user_model()


class AppointmentWorkflowTests(APITestCase):
    def setUp(self):
        # 1. Création des utilisateurs
        self.admin = User.objects.create_superuser(
            email="admin.test@clinique.fr",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="Super",
        )
        self.doctor = User.objects.create_user(
            email="doc.test@clinique.fr",
            password="DocPassword123!",
            first_name="Alexandre",
            last_name="Martin",
            role=User.Role.DOCTOR,
            specialty="Médecine Générale",
        )
        self.secretary = User.objects.create_user(
            email="sec.test@clinique.fr",
            password="SecPassword123!",
            first_name="Julie",
            last_name="Caisse",
            role=User.Role.SECRETARY,
        )

        # 2. Spécialité
        self.specialty = Specialty.objects.create(
            name="Médecine Générale",
            price=5000,
            is_active=True,
        )

        # 3. Disponibilités du médecin (Tous les jours de la semaine de 08:00 à 16:00)
        for day in range(7):
            DoctorAvailability.objects.create(
                doctor=self.doctor,
                specialty=self.specialty,
                day_of_week=day,
                start_time=datetime.time(8, 0),
                end_time=datetime.time(16, 0),
                slot_duration_minutes=30,
                is_active=True,
            )

        # Date de test future
        self.future_date = timezone.localdate() + datetime.timedelta(days=2)

    def test_public_specialties_list(self):
        """Vérifie que la liste des spécialités est publique et accessible sans token."""
        url = reverse("appointments:public_specialties")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Médecine Générale")

    def test_public_available_slots(self):
        """Vérifie le calcul des créneaux horaires disponibles."""
        url = reverse("appointments:public_slots")
        response = self.client.get(url, {
            "specialty_id": self.specialty.id,
            "date": self.future_date.isoformat(),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("slots", response.data)
        self.assertGreater(len(response.data["slots"]), 0)
        first_slot = response.data["slots"][0]
        self.assertEqual(first_slot["time"], "08:00")
        self.assertTrue(first_slot["available"])

    def test_public_booking_creates_res_reference(self):
        """Vérifie qu'un nouveau patient reçoit une référence RES-."""
        url = reverse("appointments:public_appointment_create")
        payload = {
            "first_name": "Jean-Marc",
            "last_name": "Kouadio",
            "phone_number": "0701020304",
            "email": "kouadio@test.ci",
            "specialty_id": self.specialty.id,
            "appointment_date": self.future_date.isoformat(),
            "appointment_time": "09:00",
            "reason": "Fièvre et maux de tête depuis deux jours",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data["appointment"]
        self.assertTrue(data["booking_reference"].startswith("RES-"))
        self.assertEqual(data["status"], "EN_ATTENTE")
        self.assertIsNone(data["patient"])
        self.assertTrue(data["is_new_patient"])

    def test_public_lookup_and_patient_cancellation(self):
        """Vérifie la recherche et l'annulation exclusive par le patient."""
        # Création d'un RDV
        appointment = Appointment.objects.create(
            first_name="Awa",
            last_name="Diallo",
            phone_number="0505050505",
            specialty=self.specialty,
            appointment_date=self.future_date,
            appointment_time=datetime.time(10, 0),
            status=Appointment.Status.EN_ATTENTE,
        )

        # Lookup
        lookup_url = reverse("appointments:public_appointment_lookup")
        res = self.client.post(lookup_url, {
            "reference": appointment.booking_reference,
            "phone_number": "0505050505",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

        # Annulation
        cancel_url = reverse("appointments:public_appointment_cancel")
        res_cancel = self.client.post(cancel_url, {
            "reference": appointment.booking_reference,
            "phone_number": "0505050505",
            "reason": "Imprévu professionnel",
        }, format="json")
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.ANNULE)
        self.assertEqual(appointment.cancelled_by, "PATIENT")

    def test_complete_clinical_workflow(self):
        """
        Cycle de vie complet :
        1. Réservation en ligne (EN_ATTENTE)
        2. Secrétaire confirme (CONFIRME)
        3. Arrivée au guichet : Enregistrement -> Génération IPP (PAT-), Facture d'encaissement -> EN_SALLE_D_ATTENTE
        4. Médecin démarre la consultation -> EN_CONSULTATION
        5. Médecin termine -> TERMINE
        """
        appointment = Appointment.objects.create(
            first_name="Moussa",
            last_name="Bamba",
            phone_number="0102030405",
            specialty=self.specialty,
            appointment_date=self.future_date,
            appointment_time=datetime.time(11, 0),
            status=Appointment.Status.EN_ATTENTE,
        )
        self.assertIsNone(appointment.patient)

        # 1. Connexion Secrétaire
        self.client.force_authenticate(user=self.secretary)

        # 2. Confirmation
        confirm_url = reverse("appointments:staff_appointment_confirm", kwargs={"pk": appointment.id})
        res_conf = self.client.patch(confirm_url)
        self.assertEqual(res_conf.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CONFIRME)

        # 3. Check-in guichet (Création Patient + Facture + Salle d'attente)
        checkin_url = reverse("appointments:staff_appointment_checkin", kwargs={"pk": appointment.id})
        res_checkin = self.client.patch(checkin_url)
        self.assertEqual(res_checkin.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.EN_SALLE_D_ATTENTE)
        self.assertIsNotNone(appointment.patient)
        self.assertTrue(appointment.patient.patient_number.startswith("PAT-"))
        self.assertIsNotNone(appointment.invoice)
        self.assertEqual(appointment.invoice.payment_status, Invoice.PaymentStatus.UNPAID)
        self.assertEqual(appointment.invoice.consultation_fee, 5000)

        # 4. Prise en charge par le Médecin
        self.client.force_authenticate(user=self.doctor)
        start_url = reverse("appointments:staff_appointment_start", kwargs={"pk": appointment.id})
        res_start = self.client.patch(start_url)
        self.assertEqual(res_start.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.EN_CONSULTATION)
        self.assertEqual(appointment.doctor, self.doctor)

        # 5. Clôture par le Médecin
        finish_url = reverse("appointments:staff_appointment_finish", kwargs={"pk": appointment.id})
        res_finish = self.client.patch(finish_url)
        self.assertEqual(res_finish.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.TERMINE)

    def test_reschedule_by_patient_and_staff(self):
        """Vérifie que le report est autorisé pour le patient et le personnel médical."""
        appointment = Appointment.objects.create(
            first_name="Sara",
            last_name="Touré",
            phone_number="0808080808",
            specialty=self.specialty,
            appointment_date=self.future_date,
            appointment_time=datetime.time(14, 0),
            status=Appointment.Status.CONFIRME,
        )

        # Report par la secrétaire
        self.client.force_authenticate(user=self.secretary)
        new_date = self.future_date + datetime.timedelta(days=1)
        resched_url = reverse("appointments:staff_appointment_reschedule", kwargs={"pk": appointment.id})
        res = self.client.patch(resched_url, {
            "new_date": new_date.isoformat(),
            "new_time": "15:00",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.appointment_date, new_date)
        self.assertEqual(appointment.appointment_time, datetime.time(15, 0))
        self.assertEqual(appointment.rescheduled_count, 1)
