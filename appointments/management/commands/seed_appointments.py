import datetime
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from appointments.models import Appointment, DoctorAvailability
from billing.models import Specialty

User = get_user_model()


class Command(BaseCommand):
    help = "Initialise les créneaux et disponibilités des médecins pour les tests des rendez-vous."

    def handle(self, *args, **options):
        doctor = User.objects.filter(role=User.Role.DOCTOR).first()
        if not doctor:
            self.stdout.write(self.style.WARNING("Aucun médecin trouvé. Veuillez d'abord exécuter seed_users."))
            return

        specialties = Specialty.objects.filter(is_active=True)
        if not specialties.exists():
            self.stdout.write(self.style.WARNING("Aucune spécialité trouvée. Veuillez d'abord exécuter seed_billing."))
            return

        self.stdout.write(self.style.NOTICE("--- Configuration des disponibilités hebdomadaires des médecins ---"))

        # Du Lundi (0) au Vendredi (4), 08:00 à 16:00
        created_count = 0
        for spec in specialties:
            for day in range(5):  # Lundi à Vendredi
                avail, created = DoctorAvailability.objects.get_or_create(
                    doctor=doctor,
                    specialty=spec,
                    day_of_week=day,
                    defaults={
                        "start_time": datetime.time(8, 0),
                        "end_time": datetime.time(16, 0),
                        "slot_duration_minutes": 30,
                        "is_active": True,
                    },
                )
                if created:
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ {created_count} créneaux hebdomadaires configurés pour Dr {doctor.get_full_name() or doctor.email}."
            )
        )
