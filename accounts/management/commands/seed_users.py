from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Initialise des comptes de démonstration pour chaque rôle de la clinique."

    def handle(self, *args, **options):
        demo_users = [
            {
                "email": "admin@clinique.fr",
                "first_name": "Claire",
                "last_name": "Vasseur",
                "role": User.Role.ADMIN,
                "specialty": "",
                "phone_number": "01 40 50 60 70",
                "is_staff": True,
                "is_superuser": True,
                "password": "AdminPass123!",
            },
            {
                "email": "dr.martin@clinique.fr",
                "first_name": "Alexandre",
                "last_name": "Martin",
                "role": User.Role.DOCTOR,
                "specialty": "Médecine Générale & Urgences",
                "phone_number": "01 40 50 60 71",
                "is_staff": False,
                "is_superuser": False,
                "password": "DoctorPass123!",
            },
            {
                "email": "inf.sophie@clinique.fr",
                "first_name": "Sophie",
                "last_name": "Bernard",
                "role": User.Role.NURSE,
                "specialty": "",
                "phone_number": "01 40 50 60 72",
                "is_staff": False,
                "is_superuser": False,
                "password": "NursePass123!",
            },
            {
                "email": "sec.julie@clinique.fr",
                "first_name": "Julie",
                "last_name": "Moreau",
                "role": User.Role.SECRETARY,
                "specialty": "",
                "phone_number": "01 40 50 60 73",
                "is_staff": False,
                "is_superuser": False,
                "password": "SecretaryPass123!",
            },
        ]

        for data in demo_users:
            email = data["email"]
            password = data.pop("password")
            user, created = User.objects.get_or_create(email=email, defaults=data)
            user.set_password(password)
            for k, v in data.items():
                setattr(user, k, v)
            user.save()
            action = "créé" if created else "mis à jour"
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Utilisateur [{user.get_role_display()}] {email} {action} (mdp: {password})"
                )
            )

        self.stdout.write(self.style.SUCCESS("\nInitialisation terminée avec succès !"))
