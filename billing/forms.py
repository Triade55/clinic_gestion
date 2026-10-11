from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Invoice, Patient, Specialty


class EncaissementForm(forms.Form):
    """
    Formulaire d'encaissement et d'admission utilisé par la secrétaire.
    Permet soit de créer un nouveau patient, soit de renseigner le numéro d'un patient existant.
    """
    PATIENT_TYPE_CHOICES = (
        ("NEW", _("Nouveau patient")),
        ("EXISTING", _("Patient déjà enregistré (Numéro de patient)")),
    )

    patient_mode = forms.ChoiceField(
        label=_("Statut du patient"),
        choices=PATIENT_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "radio-inline"}),
        initial="NEW",
    )

    # Pour un patient existant
    existing_patient_number = forms.CharField(
        label=_("Numéro de patient existant"),
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "ex: PAT-2026-0001",
                "id": "id_existing_patient_number",
            }
        ),
        help_text=_("Saisissez le numéro unique du patient qui lui a été attribué lors de sa première visite."),
    )

    # Pour un nouveau patient
    first_name = forms.CharField(
        label=_("Prénom du patient"),
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "ex: Moussa, Aminata...",
                "id": "id_first_name",
            }
        ),
    )
    last_name = forms.CharField(
        label=_("Nom du patient"),
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "ex: Diallo, Traoré...",
                "id": "id_last_name",
            }
        ),
    )
    phone_number = forms.CharField(
        label=_("Téléphone"),
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "ex: 07 00 00 00 00",
                "id": "id_phone_number",
            }
        ),
    )

    # Encaissement
    specialty = forms.ModelChoiceField(
        label=_("Spécialité / Type de Consultation"),
        queryset=Specialty.objects.filter(is_active=True),
        empty_label=_("--- Choisissez la spécialité ---"),
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "id": "id_specialty_select",
            }
        ),
    )
    amount_received = forms.DecimalField(
        label=_("Montant reçu du patient (FCFA)"),
        max_digits=10,
        decimal_places=0,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control amount-input",
                "placeholder": "ex: 10000",
                "id": "id_amount_received",
                "step": "500",
            }
        ),
        help_text=_("Montant en espèces ou paiement versé par le patient."),
    )

    def clean(self):
        cleaned_data = super().clean()
        patient_mode = cleaned_data.get("patient_mode")
        existing_number = cleaned_data.get("existing_patient_number")
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")
        specialty = cleaned_data.get("specialty")
        amount_received = cleaned_data.get("amount_received")

        # Validation Patient
        if patient_mode == "EXISTING":
            if not existing_number or not existing_number.strip():
                self.add_error(
                    "existing_patient_number",
                    _("Veuillez renseigner le numéro unique du patient existant."),
                )
            else:
                existing_number = existing_number.strip()
                try:
                    cleaned_data["patient_obj"] = Patient.objects.get(
                        patient_number__iexact=existing_number
                    )
                except Patient.DoesNotExist:
                    self.add_error(
                        "existing_patient_number",
                        _(f"Aucun patient trouvé avec le numéro '{existing_number}'. Vérifiez la saisie ou enregistrez-le en nouveau patient."),
                    )
        else:
            # Nouveau Patient
            if not first_name or not first_name.strip():
                self.add_error("first_name", _("Le prénom du patient est obligatoire."))
            if not last_name or not last_name.strip():
                self.add_error("last_name", _("Le nom du patient est obligatoire."))

        # Le montant perçu peut être inférieur (acompte / paiement partiel), égal ou supérieur (monnaie rendue)
        if amount_received is not None and amount_received < 0:
            self.add_error("amount_received", _("Le montant reçu ne peut pas être négatif."))

        return cleaned_data
