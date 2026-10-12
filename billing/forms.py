from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Invoice, InvoicePayment, Patient, Specialty


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


class InvoicePaymentForm(forms.Form):
    """
    Formulaire pour enregistrer un versement / acompte sur une facture non soldée.
    Permet au patient de solder la totalité ou de verser des montants partiels successifs.
    """
    amount_paid = forms.DecimalField(
        label=_("Montant du versement à imputer (FCFA)"),
        max_digits=10,
        decimal_places=0,
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control amount-input",
                "id": "id_amount_paid",
                "placeholder": "ex: 2000",
                "step": "500",
                "required": True,
            }
        ),
        help_text=_("Montant effectif déduit du reliquat restant dû."),
    )
    amount_received = forms.DecimalField(
        label=_("Espèces remises par le patient (FCFA)"),
        max_digits=10,
        decimal_places=0,
        min_value=0,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "id": "id_amount_received",
                "placeholder": "ex: 5000",
                "step": "500",
            }
        ),
        help_text=_("Optionnel : saisissez si le patient donne un billet supérieur pour calculer la monnaie."),
    )
    payment_method = forms.ChoiceField(
        label=_("Mode de règlement"),
        choices=InvoicePayment.PaymentMethod.choices,
        initial=InvoicePayment.PaymentMethod.CASH,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "id": "id_payment_method",
            }
        ),
    )
    note = forms.CharField(
        label=_("Observation / Référence"),
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "id": "id_note",
                "placeholder": "ex: Versement partiel, référence Wave...",
            }
        ),
    )

    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        if invoice:
            rem = int(invoice.amount_remaining)
            self.fields["amount_paid"].initial = rem
            self.fields["amount_paid"].widget.attrs["max"] = rem
            self.fields["amount_received"].initial = rem

    def clean_amount_paid(self):
        amount_paid = self.cleaned_data.get("amount_paid")
        if self.invoice and amount_paid is not None:
            if amount_paid <= 0:
                raise ValidationError(_("Le montant du versement doit être strictement positif."))
            if amount_paid > self.invoice.amount_remaining:
                rem_formatted = f"{int(self.invoice.amount_remaining):,}".replace(",", " ")
                raise ValidationError(
                    _(f"Le montant du versement ne peut pas dépasser le solde restant dû ({rem_formatted} FCFA).")
                )
        return amount_paid

    def clean(self):
        cleaned_data = super().clean()
        amount_paid = cleaned_data.get("amount_paid")
        amount_received = cleaned_data.get("amount_received")

        if amount_paid is not None:
            if amount_received is None or amount_received == 0:
                # Appoint exact
                cleaned_data["amount_received"] = amount_paid
                cleaned_data["amount_change"] = 0
            else:
                if amount_received < amount_paid:
                    self.add_error(
                        "amount_received",
                        _(f"Les espèces remises ({int(amount_received):,} FCFA) ne peuvent pas être inférieures au versement ({int(amount_paid):,} FCFA).".replace(",", " ")),
                    )
                else:
                    cleaned_data["amount_change"] = amount_received - amount_paid

        return cleaned_data
