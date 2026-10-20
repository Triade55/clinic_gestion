import datetime
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import User
from billing.models import Invoice, Patient, Specialty
from .models import Appointment, DoctorAvailability


class SpecialtySerializer(serializers.ModelSerializer):
    """Serializer pour afficher les spécialités et tarifs."""
    class Meta:
        model = Specialty
        fields = ["id", "name", "price", "is_active"]


class DoctorUserSimpleSerializer(serializers.ModelSerializer):
    """Représentation simplifiée d'un médecin."""
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name", "specialty"]


class DoctorAvailabilitySerializer(serializers.ModelSerializer):
    """Affichage des disponibilités des médecins."""
    doctor = DoctorUserSimpleSerializer(read_only=True)
    specialty_name = serializers.CharField(source="specialty.name", read_only=True)
    day_of_week_label = serializers.CharField(source="get_day_of_week_display", read_only=True)

    class Meta:
        model = DoctorAvailability
        fields = [
            "id",
            "doctor",
            "specialty",
            "specialty_name",
            "day_of_week",
            "day_of_week_label",
            "start_time",
            "end_time",
            "slot_duration_minutes",
            "is_active",
        ]


class DoctorAvailabilityCreateSerializer(serializers.ModelSerializer):
    """Création / mise à jour d'une disponibilité par le médecin."""
    class Meta:
        model = DoctorAvailability
        fields = [
            "id",
            "specialty",
            "day_of_week",
            "start_time",
            "end_time",
            "slot_duration_minutes",
            "is_active",
        ]

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError(
                {"end_time": _("L'heure de fin doit être postérieure à l'heure de début.")}
            )
        return attrs


class PublicAppointmentBookingSerializer(serializers.Serializer):
    """
    Serializer pour la prise de rendez-vous en ligne (accessible sans authentification).
    Gère aussi bien les nouveaux patients (génération d'un reçu RES-)
    que les patients déjà répertoriés (reconnaissance par numéro PAT ou téléphone).
    """
    first_name = serializers.CharField(max_length=100, required=True)
    last_name = serializers.CharField(max_length=100, required=True)
    phone_number = serializers.CharField(max_length=30, required=True)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    specialty_id = serializers.IntegerField(required=True)
    appointment_date = serializers.DateField(required=True)
    appointment_time = serializers.TimeField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    patient_number = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("Optionnel : renseigner si le patient a déjà un numéro de dossier PAT-XXXX"),
    )

    def validate_specialty_id(self, value):
        try:
            specialty = Specialty.objects.get(id=value, is_active=True)
        except Specialty.DoesNotExist:
            raise serializers.ValidationError(_("Spécialité invalide ou inactive."))
        return value

    def validate_appointment_date(self, value):
        today = timezone.localdate()
        if value < today:
            raise serializers.ValidationError(_("La date de rendez-vous ne peut pas être dans le passé."))
        return value

    def validate(self, attrs):
        date = attrs["appointment_date"]
        time = attrs["appointment_time"]
        specialty_id = attrs["specialty_id"]

        # Vérifier que le créneau correspond à une disponibilité médecin pour ce jour de semaine
        day_of_week = date.weekday()  # 0=Lundi, ..., 6=Dimanche
        availabilities = DoctorAvailability.objects.filter(
            specialty_id=specialty_id,
            day_of_week=day_of_week,
            is_active=True,
        )

        if not availabilities.exists():
            raise serializers.ValidationError(
                {"appointment_date": _("Aucun médecin n'est disponible pour cette spécialité ce jour-là.")}
            )

        # Vérifier si l'heure demandée est couverte par au moins une disponibilité
        matching_doctor = None
        for av in availabilities:
            if av.start_time <= time < av.end_time:
                # Vérifier si ce médecin est déjà pris sur ce créneau
                is_booked = Appointment.objects.filter(
                    doctor=av.doctor,
                    appointment_date=date,
                    appointment_time=time,
                    status__in=[
                        Appointment.Status.EN_ATTENTE,
                        Appointment.Status.CONFIRME,
                        Appointment.Status.EN_SALLE_D_ATTENTE,
                        Appointment.Status.EN_CONSULTATION,
                    ],
                ).exists()
                if not is_booked:
                    matching_doctor = av.doctor
                    break

        # Si aucun créneau strict n'est trouvé, vérifier la disponibilité générale de la spécialité
        attrs["assigned_doctor"] = matching_doctor
        return attrs

    def create(self, validated_data):
        specialty = Specialty.objects.get(id=validated_data["specialty_id"])
        patient_number = validated_data.get("patient_number", "").strip()

        patient = None
        if patient_number:
            patient = Patient.objects.filter(patient_number__iexact=patient_number).first()
        if not patient:
            # Recherche par numéro de téléphone existant
            phone = validated_data["phone_number"].strip()
            patient = Patient.objects.filter(phone_number=phone).first()

        appointment = Appointment.objects.create(
            booking_reference=Appointment.generate_booking_reference(),
            patient=patient,
            first_name=validated_data["first_name"].strip(),
            last_name=validated_data["last_name"].strip(),
            phone_number=validated_data["phone_number"].strip(),
            email=validated_data.get("email", "").strip(),
            specialty=specialty,
            doctor=validated_data.get("assigned_doctor"),
            appointment_date=validated_data["appointment_date"],
            appointment_time=validated_data["appointment_time"],
            reason=validated_data.get("reason", "").strip(),
            status=Appointment.Status.EN_ATTENTE,
        )
        return appointment


class PublicAppointmentLookupSerializer(serializers.Serializer):
    """Recherche d'un rendez-vous par sa référence et son téléphone."""
    reference = serializers.CharField(required=True, help_text=_("Code RES-XXXX ou PAT-XXXX"))
    phone_number = serializers.CharField(required=True)


class PublicAppointmentRescheduleSerializer(serializers.Serializer):
    """Report d'un rendez-vous par le patient."""
    reference = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)
    new_date = serializers.DateField(required=True)
    new_time = serializers.TimeField(required=True)

    def validate_new_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError(_("La nouvelle date ne peut pas être dans le passé."))
        return value


class PublicAppointmentCancelSerializer(serializers.Serializer):
    """Annulation d'un rendez-vous par le patient."""
    reference = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Détails complets d'un rendez-vous."""
    specialty_name = serializers.CharField(source="specialty.name", read_only=True)
    specialty_price = serializers.DecimalField(
        source="specialty.price", max_digits=10, decimal_places=0, read_only=True
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    doctor_name = serializers.SerializerMethodField()
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True, default=None)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True, default=None)
    is_new_patient = serializers.BooleanField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "booking_reference",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "email",
            "specialty",
            "specialty_name",
            "specialty_price",
            "doctor",
            "doctor_name",
            "patient",
            "patient_number",
            "is_new_patient",
            "appointment_date",
            "appointment_time",
            "reason",
            "status",
            "status_label",
            "invoice",
            "invoice_number",
            "rescheduled_count",
            "cancelled_by",
            "cancellation_reason",
            "created_at",
            "updated_at",
        ]

    def get_doctor_name(self, obj):
        if obj.doctor:
            return f"Dr {obj.doctor.get_full_name() or obj.doctor.email}"
        return None


class StaffRescheduleSerializer(serializers.Serializer):
    """Serializer pour le report de rendez-vous par le personnel médical."""
    new_date = serializers.DateField(required=True)
    new_time = serializers.TimeField(required=True)
    doctor_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_new_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError(_("La nouvelle date ne peut pas être dans le passé."))
        return value
