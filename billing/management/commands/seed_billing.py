from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from billing.models import Invoice, Patient, Specialty

User = get_user_model()


class Command(BaseCommand):
    help = "Initialise les spécialités médicales avec leurs tarifs en FCFA et quelques patients/factures de test."

    def handle(self, *args, **options):
        # 1. Spécialités et Tarifs (FCFA)
        specialties_data = [
            {"name": "Médecine Générale", "price": 5000},
            {"name": "Pédiatrie", "price": 7500},
            {"name": "Gynécologie & Obstétrique", "price": 10000},
            {"name": "Cardiologie", "price": 15000},
            {"name": "Ophtalmologie", "price": 10000},
            {"name": "Dermatologie", "price": 8000},
            {"name": "Chirurgie Générale (Consultation)", "price": 12500},
            {"name": "Consultation d'Urgence", "price": 7000},
        ]

        self.stdout.write(self.style.NOTICE("--- Enregistrement des Spécialités et Tarifs ---"))
        specialties_map = {}
        for item in specialties_data:
            spec, created = Specialty.objects.get_or_create(
                name=item["name"],
                defaults={"price": item["price"], "is_active": True},
            )
            if not created and spec.price != item["price"]:
                spec.price = item["price"]
                spec.save()
            specialties_map[spec.name] = spec
            status = "créée" if created else "mise à jour"
            self.stdout.write(f"✓ Spécialité : {spec.name} -> {int(spec.price):,} FCFA ({status})")

        # 2. Patients de test
        self.stdout.write(self.style.NOTICE("\n--- Création de Patients de Test ---"))
        test_patients = [
            {
                "patient_number": "PAT-2026-0001",
                "first_name": "Amadou",
                "last_name": "Koné",
                "phone_number": "07 45 88 12 01",
            },
            {
                "patient_number": "PAT-2026-0002",
                "first_name": "Fatoumata",
                "last_name": "Traoré",
                "phone_number": "05 12 34 56 78",
            },
            {
                "patient_number": "PAT-2026-0003",
                "first_name": "Yao",
                "last_name": "Kouassi",
                "phone_number": "01 98 76 54 32",
            },
        ]

        created_patients = []
        for pdata in test_patients:
            patient, created = Patient.objects.get_or_create(
                patient_number=pdata["patient_number"],
                defaults=pdata,
            )
            created_patients.append(patient)
            action = "créé" if created else "existant"
            self.stdout.write(f"✓ Patient [{patient.patient_number}] {patient.full_name} ({action})")

        # 3. Facture de démonstration pour la secrétaire
        secretary_user = User.objects.filter(role=User.Role.SECRETARY).first() or User.objects.first()

        if not Invoice.objects.exists() and secretary_user:
            spec_mg = specialties_map.get("Médecine Générale")
            if spec_mg and created_patients:
                inv = Invoice.objects.create(
                    patient=created_patients[0],
                    specialty=spec_mg,
                    consultation_fee=spec_mg.price,
                    amount_received=10000,
                    amount_change=5000,
                    created_by=secretary_user,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Facture témoin créée : {inv.invoice_number} | "
                        f"Patient: {inv.patient.full_name} | Reçu: 10 000 FCFA | Rendu: 5 000 FCFA"
                    )
                )

        self.stdout.write(self.style.SUCCESS("\nInitialisation de la facturation réussie avec succès !"))
