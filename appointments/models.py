import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from billing.models import Invoice, Patient, Specialty


class DoctorAvailability(models.Model):
    """
    Plage horaire de disponibilité hebdomadaire d'un médecin pour une spécialité donnée.
    Permet de générer dynamiquement les créneaux de consultation disponibles.
    """
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, _("Lundi")
        TUESDAY = 1, _("Mardi")
        WEDNESDAY = 2, _("Mercredi")
        THURSDAY = 3, _("Jeudi")
        FRIDAY = 4, _("Vendredi")
        SATURDAY = 5, _("Samedi")
        SUNDAY = 6, _("Dimanche")

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availabilities",
        verbose_name=_("Médecin"),
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.CASCADE,
        related_name="doctor_availabilities",
        verbose_name=_("Spécialité"),
    )
    day_of_week = models.IntegerField(
        _("Jour de la semaine"),
        choices=DayOfWeek.choices,
    )
    start_time = models.TimeField(_("Heure de début"))
    end_time = models.TimeField(_("Heure de fin"))
    slot_duration_minutes = models.PositiveIntegerField(
        _("Durée du créneau (minutes)"),
        default=30,
        help_text=_("Durée en minutes par créneau de consultation"),
    )
    is_active = models.BooleanField(_("Actif"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Disponibilité Médecin")
        verbose_name_plural = _("Disponibilités Médecins")
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        day_label = self.get_day_of_week_display()
        return (
            f"Dr {self.doctor.get_full_name() or self.doctor.email} — "
            f"{self.specialty.name} ({day_label} {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"
        )

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError(
                {"end_time": _("L'heure de fin doit être postérieure à l'heure de début.")}
            )


class Appointment(models.Model):
    """
    Rendez-vous médical pris en ligne ou à la clinique.
    Suivi du statut de la demande jusqu'à la fin de la consultation.
    """
    class Status(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", _("En attente de confirmation")
        CONFIRME = "CONFIRME", _("Confirmé")
        EN_SALLE_D_ATTENTE = "EN_SALLE_D_ATTENTE", _("En salle d'attente")
        EN_CONSULTATION = "EN_CONSULTATION", _("En consultation")
        TERMINE = "TERMINE", _("Terminé")
        ANNULE = "ANNULE", _("Annulé")
        ABSENT = "ABSENT", _("Absent / Non honoré")

    booking_reference = models.CharField(
        _("Numéro de réservation"),
        max_length=30,
        unique=True,
        db_index=True,
        help_text=_("Code de réservation pour le patient (ex: RES-202610-0001)"),
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name=_("Dossier Patient"),
        help_text=_("Rattaché une fois le patient enregistré ou existant (IPP PAT-XXXX)"),
    )
    first_name = models.CharField(_("Prénom"), max_length=100)
    last_name = models.CharField(_("Nom"), max_length=100)
    phone_number = models.CharField(_("Numéro de téléphone"), max_length=30, db_index=True)
    email = models.EmailField(_("Adresse email"), blank=True)

    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name=_("Spécialité demandée"),
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doctor_appointments",
        verbose_name=_("Médecin assigné / consultant"),
    )
    appointment_date = models.DateField(_("Date du rendez-vous"), db_index=True)
    appointment_time = models.TimeField(_("Heure du rendez-vous"))

    reason = models.TextField(
        _("Motif / Symptômes décrits par le patient"),
        blank=True,
        help_text=_("Facultatif à la réservation (sera alimenté par IA dans la V2)"),
    )
    status = models.CharField(
        _("Statut du rendez-vous"),
        max_length=30,
        choices=Status.choices,
        default=Status.EN_ATTENTE,
        db_index=True,
    )
    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointment",
        verbose_name=_("Facture d'encaissement associée"),
    )
    cancellation_reason = models.TextField(
        _("Motif d'annulation"),
        blank=True,
    )
    cancelled_by = models.CharField(
        _("Annulé par"),
        max_length=30,
        blank=True,
    )
    rescheduled_count = models.PositiveIntegerField(
        _("Nombre de reports"),
        default=0,
    )
    created_at = models.DateTimeField(_("Date de création"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Dernière mise à jour"), auto_now=True)

    class Meta:
        verbose_name = _("Rendez-vous")
        verbose_name_plural = _("Rendez-vous")
        ordering = ["appointment_date", "appointment_time"]

    def __str__(self):
        return f"[{self.booking_reference}] {self.last_name.upper()} {self.first_name} — {self.appointment_date} {self.appointment_time.strftime('%H:%M')} ({self.get_status_display()})"

    @property
    def full_name(self):
        return f"{self.last_name.upper()} {self.first_name}"

    @property
    def is_new_patient(self):
        return self.patient is None

    @classmethod
    def generate_booking_reference(cls):
        """Génère le prochain numéro séquentiel de réservation au format RES-YYYYMM-XXXX."""
        now = datetime.datetime.now()
        prefix = f"RES-{now.strftime('%Y%m')}-"
        last = cls.objects.filter(booking_reference__startswith=prefix).order_by("-id").first()
        if last and last.booking_reference:
            try:
                seq = int(last.booking_reference.replace(prefix, "")) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            self.booking_reference = self.generate_booking_reference()
        super().save(*args, **kwargs)

    def confirm(self):
        """Validation du RDV par la secrétaire (EN_ATTENTE -> CONFIRME)."""
        if self.status != self.Status.EN_ATTENTE:
            raise ValidationError(_("Seul un rendez-vous en attente peut être confirmé."))
        self.status = self.Status.CONFIRME
        self.save(update_fields=["status", "updated_at"])

    def checkin(self, secretary_user=None):
        """
        Arrivée du patient au guichet :
        - S'il n'avait pas de numéro PAT, création officielle du dossier Patient.
        - Génération automatique de la facture de consultation à l'état NON RÉGLÉ.
        - Passage en salle d'attente (CONFIRME -> EN_SALLE_D_ATTENTE).
        """
        if self.status not in (self.Status.CONFIRME, self.Status.EN_ATTENTE):
            raise ValidationError(
                _("Le patient doit avoir un rendez-vous confirmé ou en attente pour être enregistré en salle d'attente.")
            )

        with transaction.atomic():
            # 1. Enregistrement officiel du Patient si nouveau
            if not self.patient:
                patient = Patient.objects.create(
                    patient_number=Patient.generate_patient_number(),
                    first_name=self.first_name.strip(),
                    last_name=self.last_name.strip(),
                    phone_number=self.phone_number.strip(),
                )
                self.patient = patient

            # 2. Création de la facture de consultation au guichet si pas encore créée
            if not self.invoice:
                invoice = Invoice.objects.create(
                    patient=self.patient,
                    specialty=self.specialty,
                    consultation_fee=self.specialty.price,
                    amount_received=0,
                    amount_change=0,
                    amount_remaining=self.specialty.price,
                    payment_status=Invoice.PaymentStatus.UNPAID,
                    created_by=secretary_user,
                )
                self.invoice = invoice

            self.status = self.Status.EN_SALLE_D_ATTENTE
            self.save(update_fields=["patient", "invoice", "status", "updated_at"])

    def start_consultation(self, doctor_user):
        """Prise en charge du patient par le médecin (EN_SALLE_D_ATTENTE -> EN_CONSULTATION)."""
        if self.status != self.Status.EN_SALLE_D_ATTENTE:
            raise ValidationError(
                _("Le patient doit être en salle d'attente pour démarrer la consultation.")
            )
        self.doctor = doctor_user
        self.status = self.Status.EN_CONSULTATION
        self.save(update_fields=["doctor", "status", "updated_at"])

    def finish_consultation(self, doctor_user=None):
        """Clôture de la consultation par le médecin (EN_CONSULTATION -> TERMINE)."""
        if self.status != self.Status.EN_CONSULTATION:
            raise ValidationError(
                _("Seule une consultation en cours peut être terminée.")
            )
        self.status = self.Status.TERMINE
        self.save(update_fields=["status", "updated_at"])

    def cancel_by_patient(self, reason=""):
        """
        Annulation exclusive par le patient.
        Interdite aux secrétaires et docteurs selon la règle métier.
        """
        if self.status in (self.Status.TERMINE, self.Status.ANNULE, self.Status.EN_CONSULTATION):
            raise ValidationError(
                _("Ce rendez-vous ne peut plus être annulé dans son état actuel.")
            )
        self.status = self.Status.ANNULE
        self.cancelled_by = "PATIENT"
        self.cancellation_reason = reason
        self.save(update_fields=["status", "cancelled_by", "cancellation_reason", "updated_at"])

    def reschedule(self, new_date, new_time):
        """
        Report de rendez-vous (autorisé pour Patient, Secrétaire et Médecin).
        """
        if self.status in (self.Status.TERMINE, self.Status.ANNULE, self.Status.EN_CONSULTATION):
            raise ValidationError(
                _("Impossible de reporter un rendez-vous déjà en cours, terminé ou annulé.")
            )
        self.appointment_date = new_date
        self.appointment_time = new_time
        self.rescheduled_count += 1
        # Si le rendez-vous était confirmé, il reste confirmé à la nouvelle date
        self.save(update_fields=["appointment_date", "appointment_time", "rescheduled_count", "updated_at"])
