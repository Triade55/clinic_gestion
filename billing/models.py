import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Specialty(models.Model):
    """
    Spécialités médicales et tarifs de consultation associés.
    """
    name = models.CharField(_("Nom de la spécialité"), max_length=120, unique=True)
    price = models.DecimalField(
        _("Tarif de consultation (FCFA)"),
        max_digits=10,
        decimal_places=0,
        help_text=_("Montant en Franc CFA"),
    )
    is_active = models.BooleanField(_("Actif"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Spécialité médicale")
        verbose_name_plural = _("Spécialités médicales")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} — {int(self.price):,} FCFA".replace(",", " ")


class Patient(models.Model):
    """
    Identité administrative minimale du patient enregistrée par la secrétaire.
    Chaque patient possède un numéro unique permanent (IPP) qui l'accompagne.
    """
    patient_number = models.CharField(
        _("Numéro Unique de Patient"),
        max_length=30,
        unique=True,
        db_index=True,
        help_text=_("Identifiant permanent unique (ex: PAT-2026-0001)"),
    )
    first_name = models.CharField(_("Prénom"), max_length=100)
    last_name = models.CharField(_("Nom"), max_length=100)
    phone_number = models.CharField(_("Numéro de téléphone"), max_length=30, blank=True)
    created_at = models.DateTimeField(_("Date d'enregistrement"), auto_now_add=True)

    class Meta:
        verbose_name = _("Patient")
        verbose_name_plural = _("Patients")
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.patient_number}] {self.last_name.upper()} {self.first_name}"

    @property
    def full_name(self):
        return f"{self.last_name.upper()} {self.first_name}"

    @classmethod
    def generate_patient_number(cls):
        """Génère le prochain numéro unique de patient séquentiel au format PAT-YYYY-XXXX."""
        year = datetime.date.today().year
        prefix = f"PAT-{year}-"
        last = cls.objects.filter(patient_number__startswith=prefix).order_by("-id").first()
        if last and last.patient_number:
            try:
                seq = int(last.patient_number.replace(prefix, "")) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"


class Invoice(models.Model):
    """
    Encaissement et Facture de consultation émise par la secrétaire.
    Le montant perçu peut être supérieur (monnaie rendue), égal (soldé),
    ou inférieur au tarif (paiement partiel / reliquat restant dû).
    """
    class PaymentStatus(models.TextChoices):
        PAID = "PAID", _("Soldé / Réglé en totalité")
        PARTIAL = "PARTIAL", _("Paiement partiel / Acompte")
        UNPAID = "UNPAID", _("Non réglé")

    invoice_number = models.CharField(
        _("Numéro de facture"),
        max_length=30,
        unique=True,
        db_index=True,
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name=_("Patient"),
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name=_("Spécialité / Consultation"),
    )
    consultation_fee = models.DecimalField(
        _("Montant consultation (FCFA)"),
        max_digits=10,
        decimal_places=0,
    )
    amount_received = models.DecimalField(
        _("Montant reçu du patient (FCFA)"),
        max_digits=10,
        decimal_places=0,
        default=0,
    )
    amount_change = models.DecimalField(
        _("Montant rendu (FCFA)"),
        max_digits=10,
        decimal_places=0,
        default=0,
    )
    amount_remaining = models.DecimalField(
        _("Reste à payer (FCFA)"),
        max_digits=10,
        decimal_places=0,
        default=0,
    )
    payment_status = models.CharField(
        _("Statut du règlement"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PAID,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invoices",
        verbose_name=_("Secrétaire de caisse"),
    )
    created_at = models.DateTimeField(_("Date et heure d'encaissement"), auto_now_add=True)

    class Meta:
        verbose_name = _("Facture / Encaissement")
        verbose_name_plural = _("Factures / Encaissements")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Facture {self.invoice_number} - {self.patient.full_name} ({int(self.consultation_fee):,} FCFA)"

    def clean(self):
        if self.amount_received is not None and self.amount_received < 0:
            raise ValidationError(
                {"amount_received": _("Le montant reçu ne peut pas être négatif.")}
            )

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()

        if self.consultation_fee is not None and self.amount_received is not None:
            if self.amount_received >= self.consultation_fee:
                self.amount_change = self.amount_received - self.consultation_fee
                self.amount_remaining = 0
                self.payment_status = self.PaymentStatus.PAID
            elif self.amount_received > 0:
                self.amount_change = 0
                self.amount_remaining = self.consultation_fee - self.amount_received
                self.payment_status = self.PaymentStatus.PARTIAL
            else:
                self.amount_change = 0
                self.amount_remaining = self.consultation_fee
                self.payment_status = self.PaymentStatus.UNPAID

        super().save(*args, **kwargs)

    @classmethod
    def generate_invoice_number(cls):
        """Génère le prochain numéro séquentiel de facture au format FAC-YYYYMM-XXXX."""
        now = datetime.datetime.now()
        prefix = f"FAC-{now.strftime('%Y%m')}-"
        last = cls.objects.filter(invoice_number__startswith=prefix).order_by("-id").first()
        if last and last.invoice_number:
            try:
                seq = int(last.invoice_number.replace(prefix, "")) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"
