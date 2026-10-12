import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
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

    def add_payment(
        self,
        amount_paid,
        amount_received=None,
        amount_change=0,
        payment_method="ESPECES",
        note="",
        created_by=None,
    ):
        """
        Enregistre un versement / règlement sur cette facture.
        Met à jour le total perçu, le solde restant dû et le statut de la facture.
        """
        if amount_paid <= 0:
            raise ValidationError(_("Le montant du versement doit être supérieur à zéro."))
        if amount_paid > self.amount_remaining:
            raise ValidationError(
                _(f"Le montant du versement ({int(amount_paid)} FCFA) ne peut pas excéder le reliquat restant dû ({int(self.amount_remaining)} FCFA).")
            )

        if amount_received is None:
            amount_received = amount_paid

        payment = InvoicePayment.objects.create(
            invoice=self,
            amount_paid=amount_paid,
            amount_received=amount_received,
            amount_change=amount_change,
            payment_method=payment_method,
            note=note,
            created_by=created_by,
        )

        total_paid = self.payments.aggregate(total=models.Sum("amount_paid"))["total"] or 0
        self.amount_received = total_paid
        self.amount_remaining = max(0, self.consultation_fee - total_paid)
        if self.amount_remaining == 0:
            self.payment_status = self.PaymentStatus.PAID
        else:
            self.payment_status = self.PaymentStatus.PARTIAL
        super().save(update_fields=["amount_received", "amount_remaining", "payment_status"])
        return payment


class InvoicePayment(models.Model):
    """
    Règlement ou versement partiel/total d'une facture.
    Permet aux patients de régler un acompte initial, puis de revenir plus tard
    effectuer des versements successifs jusqu'au solde complet du montant dû.
    """
    class PaymentMethod(models.TextChoices):
        CASH = "ESPECES", _("Espèces")
        WAVE = "WAVE", _("Wave")
        ORANGE_MONEY = "ORANGE_MONEY", _("Orange Money")
        MTN_MONEY = "MTN_MONEY", _("MTN Mobile Money")
        MOOV_MONEY = "MOOV_MONEY", _("Moov Money")
        CARD = "CARTE", _("Carte bancaire")
        TRANSFER = "VIREMENT", _("Virement")

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("Facture"),
    )
    payment_number = models.CharField(
        _("Numéro de reçu de versement"),
        max_length=30,
        unique=True,
        db_index=True,
    )
    amount_paid = models.DecimalField(
        _("Montant imputé / versé (FCFA)"),
        max_digits=10,
        decimal_places=0,
        help_text=_("Montant effectif déduit du reliquat restant dû"),
    )
    amount_received = models.DecimalField(
        _("Montant remis en espèces (FCFA)"),
        max_digits=10,
        decimal_places=0,
        default=0,
        help_text=_("Somme remise par le patient pour le calcul de la monnaie rendue"),
    )
    amount_change = models.DecimalField(
        _("Monnaie rendue (FCFA)"),
        max_digits=10,
        decimal_places=0,
        default=0,
    )
    payment_method = models.CharField(
        _("Mode de paiement"),
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    note = models.CharField(
        _("Observation / Référence"),
        max_length=255,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_payments",
        verbose_name=_("Encaissé par"),
    )
    created_at = models.DateTimeField(
        _("Date et heure du versement"),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _("Versement / Règlement")
        verbose_name_plural = _("Versements / Règlements")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Versement {self.payment_number} — {int(self.amount_paid):,} FCFA (Facture {self.invoice.invoice_number})"

    def clean(self):
        if self.amount_paid is not None and self.amount_paid <= 0:
            raise ValidationError({"amount_paid": _("Le montant du versement doit être supérieur à zéro.")})

    @classmethod
    def generate_payment_number(cls):
        """Génère le prochain numéro séquentiel de versement au format PAY-YYYYMM-XXXX."""
        now = datetime.datetime.now()
        prefix = f"PAY-{now.strftime('%Y%m')}-"
        last = cls.objects.filter(payment_number__startswith=prefix).order_by("-id").first()
        if last and last.payment_number:
            try:
                seq = int(last.payment_number.replace(prefix, "")) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = self.generate_payment_number()
        super().save(*args, **kwargs)


@receiver(post_save, sender=Invoice)
def create_initial_invoice_payment(sender, instance, created, **kwargs):
    """
    Crée automatiquement le premier reçu de versement si un acompte ou un paiement
    a été perçu lors de la création de la facture à l'accueil.
    """
    if created and instance.amount_received is not None and instance.amount_received > 0:
        if not instance.payments.exists():
            net_paid = min(instance.amount_received, instance.consultation_fee)
            InvoicePayment.objects.create(
                invoice=instance,
                amount_paid=net_paid,
                amount_received=instance.amount_received,
                amount_change=instance.amount_change,
                payment_method=InvoicePayment.PaymentMethod.CASH,
                note=_("Paiement initial lors de l'encaissement"),
                created_by=instance.created_by,
            )

