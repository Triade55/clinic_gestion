import datetime
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from billing.models import Specialty
from .models import Appointment, DoctorAvailability
from .permissions import IsClinicStaff, IsDoctorUser, IsSecretaryOrAdmin
from .serializers import (
    AppointmentDetailSerializer,
    DoctorAvailabilityCreateSerializer,
    DoctorAvailabilitySerializer,
    PublicAppointmentBookingSerializer,
    PublicAppointmentCancelSerializer,
    PublicAppointmentLookupSerializer,
    PublicAppointmentRescheduleSerializer,
    SpecialtySerializer,
    StaffRescheduleSerializer,
)


# ============================================================================
# ENDPOINTS PUBLICS (ACCESSIBLES PAR LE FRONTEND PATIENT SANS AUTHENTIFICATION)
# ============================================================================

class PublicSpecialtyListView(generics.ListAPIView):
    """
    GET /api/public/specialties/
    Retourne la liste des spécialités médicales actives et leurs tarifs de consultation en FCFA.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = SpecialtySerializer
    queryset = Specialty.objects.filter(is_active=True).order_by("name")
    pagination_class = None


class PublicAvailableSlotsView(APIView):
    """
    GET /api/public/slots/?specialty_id=1&date=2026-10-21
    Génère dynamiquement les créneaux horaires disponibles pour une spécialité à une date donnée.
    Prend en compte les disponibilités déclarées par les médecins et exclut les créneaux déjà réservés.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        specialty_id = request.query_params.get("specialty_id")
        date_str = request.query_params.get("date")

        if not specialty_id or not date_str:
            return Response(
                {"detail": _("Les paramètres 'specialty_id' et 'date' (YYYY-MM-DD) sont requis.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return Response(
                {"detail": _("Format de date invalide. Utilisez YYYY-MM-DD.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if target_date < timezone.localdate():
            return Response(
                {"detail": _("La date ne peut pas être dans le passé.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        day_of_week = target_date.weekday()
        availabilities = DoctorAvailability.objects.filter(
            specialty_id=specialty_id,
            day_of_week=day_of_week,
            is_active=True,
        ).select_related("doctor")

        if not availabilities.exists():
            return Response({
                "date": date_str,
                "specialty_id": int(specialty_id),
                "message": _("Aucun médecin disponible pour cette spécialité à cette date."),
                "slots": [],
            })

        # Récupérer les réservations existantes pour cette date et cette spécialité
        existing_appointments = Appointment.objects.filter(
            specialty_id=specialty_id,
            appointment_date=target_date,
            status__in=[
                Appointment.Status.EN_ATTENTE,
                Appointment.Status.CONFIRME,
                Appointment.Status.EN_SALLE_D_ATTENTE,
                Appointment.Status.EN_CONSULTATION,
            ],
        ).values("appointment_time", "doctor_id")

        booked_map = {}
        for app in existing_appointments:
            t = app["appointment_time"].strftime("%H:%M")
            doc_id = app["doctor_id"]
            if t not in booked_map:
                booked_map[t] = set()
            if doc_id:
                booked_map[t].add(doc_id)

        all_slots = []
        for av in availabilities:
            slot_delta = datetime.timedelta(minutes=av.slot_duration_minutes)
            cur = datetime.datetime.combine(target_date, av.start_time)
            end = datetime.datetime.combine(target_date, av.end_time)

            while cur + slot_delta <= end:
                slot_time_str = cur.strftime("%H:%M")
                slot_time = cur.time()

                # Vérifier si ce créneau est déjà pris pour ce médecin
                is_taken = False
                if slot_time_str in booked_map:
                    if av.doctor_id in booked_map[slot_time_str]:
                        is_taken = True

                all_slots.append({
                    "time": slot_time_str,
                    "doctor_id": av.doctor_id,
                    "doctor_name": f"Dr {av.doctor.get_full_name() or av.doctor.email}",
                    "available": not is_taken,
                })
                cur += slot_delta

        # Trier et regrouper les créneaux par heure
        slots_by_time = {}
        for s in all_slots:
            t = s["time"]
            if t not in slots_by_time:
                slots_by_time[t] = {
                    "time": t,
                    "available": False,
                    "available_doctors_count": 0,
                }
            if s["available"]:
                slots_by_time[t]["available"] = True
                slots_by_time[t]["available_doctors_count"] += 1

        sorted_slots = sorted(slots_by_time.values(), key=lambda x: x["time"])

        return Response({
            "date": date_str,
            "specialty_id": int(specialty_id),
            "total_slots": len(sorted_slots),
            "slots": sorted_slots,
        })


class PublicAppointmentCreateView(APIView):
    """
    POST /api/public/appointments/
    Prise de rendez-vous en ligne sans authentification préalable.
    Renvoie le reçu avec le numéro de réservation RES-YYYYMM-XXXX.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PublicAppointmentBookingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        appointment = serializer.save()
        detail_serializer = AppointmentDetailSerializer(appointment)
        return Response(
            {
                "message": _("Votre demande de rendez-vous a été enregistrée avec succès."),
                "booking_reference": appointment.booking_reference,
                "appointment": detail_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicAppointmentLookupView(APIView):
    """
    POST /api/public/appointments/lookup/
    Permet au patient de consulter ses rendez-vous en fournissant :
    - soit sa référence de réservation (RES-XXXX)
    - soit son numéro de patient IPP (PAT-XXXX)
    accompagné obligatoirement de son numéro de téléphone.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PublicAppointmentLookupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ref = serializer.validated_data["reference"].strip()
        phone = serializer.validated_data["phone_number"].strip()

        appointments = Appointment.objects.filter(
            Q(booking_reference__iexact=ref) | Q(patient__patient_number__iexact=ref),
            phone_number=phone,
        ).order_by("-appointment_date", "-appointment_time")

        if not appointments.exists():
            return Response(
                {"detail": _("Aucun rendez-vous trouvé avec cette référence et ce numéro de téléphone.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(AppointmentDetailSerializer(appointments, many=True).data)


class PublicAppointmentRescheduleView(APIView):
    """
    PATCH /api/public/appointments/reschedule/
    Permet au patient de reporter son propre rendez-vous en ligne.
    Nécessite la référence et le téléphone pour vérification d'identité.
    """
    permission_classes = [permissions.AllowAny]

    def patch(self, request):
        serializer = PublicAppointmentRescheduleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ref = serializer.validated_data["reference"].strip()
        phone = serializer.validated_data["phone_number"].strip()
        new_date = serializer.validated_data["new_date"]
        new_time = serializer.validated_data["new_time"]

        appointment = Appointment.objects.filter(
            Q(booking_reference__iexact=ref) | Q(patient__patient_number__iexact=ref),
            phone_number=phone,
        ).first()

        if not appointment:
            return Response(
                {"detail": _("Rendez-vous introuvable.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            appointment.reschedule(new_date=new_date, new_time=new_time)
        except DjangoValidationError as e:
            return Response({"detail": e.messages if hasattr(e, "messages") else str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": _("Rendez-vous reporté avec succès."),
            "appointment": AppointmentDetailSerializer(appointment).data,
        })


class PublicAppointmentCancelView(APIView):
    """
    POST /api/public/appointments/cancel/
    Annulation d'un rendez-vous par le patient.
    Règle stricte : SEUL le patient a le droit d'annuler.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PublicAppointmentCancelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ref = serializer.validated_data["reference"].strip()
        phone = serializer.validated_data["phone_number"].strip()
        reason = serializer.validated_data.get("reason", "")

        appointment = Appointment.objects.filter(
            Q(booking_reference__iexact=ref) | Q(patient__patient_number__iexact=ref),
            phone_number=phone,
        ).first()

        if not appointment:
            return Response(
                {"detail": _("Rendez-vous introuvable.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            appointment.cancel_by_patient(reason=reason)
        except DjangoValidationError as e:
            return Response({"detail": e.messages if hasattr(e, "messages") else str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": _("Rendez-vous annulé avec succès."),
            "appointment": AppointmentDetailSerializer(appointment).data,
        })


# ============================================================================
# ENDPOINTS INTERNES (PERSONNEL CLINIQUE : JWT AUTHENTICATED)
# ============================================================================

class StaffAppointmentListView(generics.ListAPIView):
    """
    GET /api/appointments/
    Liste des rendez-vous avec filtres avancés (date, statut, spécialité, médecin, recherche texte).
    Accessible à tout le personnel médical connecté.
    """
    permission_classes = [IsClinicStaff]
    serializer_class = AppointmentDetailSerializer

    def get_queryset(self):
        qs = Appointment.objects.select_related("patient", "specialty", "doctor", "invoice").all()

        date = self.request.query_params.get("date")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        status_filter = self.request.query_params.get("status")
        specialty_id = self.request.query_params.get("specialty_id")
        doctor_id = self.request.query_params.get("doctor_id")
        search = self.request.query_params.get("search")

        if date:
            qs = qs.filter(appointment_date=date)
        if date_from:
            qs = qs.filter(appointment_date__gte=date_from)
        if date_to:
            qs = qs.filter(appointment_date__lte=date_to)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if specialty_id:
            qs = qs.filter(specialty_id=specialty_id)
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        if search:
            qs = qs.filter(
                Q(booking_reference__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(patient__patient_number__icontains=search)
            )

        return qs.order_by("appointment_date", "appointment_time")


class StaffAppointmentDetailView(generics.RetrieveAPIView):
    """
    GET /api/appointments/{id}/
    Détail d'un rendez-vous.
    """
    permission_classes = [IsClinicStaff]
    serializer_class = AppointmentDetailSerializer
    queryset = Appointment.objects.select_related("patient", "specialty", "doctor", "invoice").all()


class StaffAppointmentConfirmView(APIView):
    """
    PATCH /api/appointments/{id}/confirm/
    Confirmation du rendez-vous par la secrétaire (EN_ATTENTE -> CONFIRME).
    """
    permission_classes = [IsSecretaryOrAdmin]

    def patch(self, request, pk):
        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return Response({"detail": _("Rendez-vous introuvable.")}, status=status.HTTP_404_NOT_FOUND)

        try:
            appointment.confirm()
        except DjangoValidationError as e:
            return Response({"detail": e.messages if hasattr(e, "messages") else str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": _("Rendez-vous confirmé avec succès."),
            "appointment": AppointmentDetailSerializer(appointment).data,
        })


class StaffAppointmentCheckinView(APIView):
    """
    PATCH /api/appointments/{id}/checkin/
    Enregistrement au guichet par la secrétaire :
    - Si le patient n'était pas répertorié, crée son dossier officiel (IPP PAT-XXXX).
    - Génère automatiquement la facture d'encaissement (Invoice) à régler au guichet.
    - Fait passer le statut en 'EN_SALLE_D_ATTENTE'.
    """
    permission_classes = [IsSecretaryOrAdmin]

    def patch(self, request, pk):
        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return Response({"detail": _("Rendez-vous introuvable.")}, status=status.HTTP_404_NOT_FOUND)

        try:
            appointment.checkin(secretary_user=request.user)
        except DjangoValidationError as e:
            return Response({"detail": e.messages if hasattr(e, "messages") else str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": _("Patient enregistré avec succès et orienté vers la salle d'attente."),
            "patient_number": appointment.patient.patient_number if appointment.patient else None,
            "invoice_number": appointment.invoice.invoice_number if appointment.invoice else None,
            "appointment": AppointmentDetailSerializer(appointment).data,
        })


class StaffAppointmentStartConsultationView(APIView):
    """
    PATCH /api/appointments/{id}/start/
    Prise en charge du patient par le médecin (EN_SALLE_D_ATTENTE -> EN_CONSULTATION).
    """
    permission_classes = [IsDoctorUser]

    def patch(self, request, pk):
        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return Response({"detail": _("Rendez-vous introuvable.")}, status=status.HTTP_404_NOT_FOUND)

        try:
            appointment.start_consultation(doctor_user=request.user)
        except DjangoValidationError as e:
            return Response({"detail": e.messages if hasattr(e, "messages") else str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": _("Consultation démarrée."),
            "appointment": AppointmentDetailSerializer(appointment).data,
        })


class StaffAppointmentFinishConsultationView(APIView):
    """
    PATCH /api/appointments/{id}/finish/
    Fin de consultation par le médecin (EN_CONSULTATION -> TERMINE).
    """
    permission_classes = [IsDoctorUser]

    def patch(self, request, pk):
        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return Response({"detail": _("Rendez-vous introuvable.")}, status=status.HTTP_404_NOT_FOUND)

        try:
            appointment.finish_consultation(doctor_user=request.user)
        except DjangoValidationError as e:
            return Response({"detail": e.messages if hasattr(e, "messages") else str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": _("Consultation clôturée avec succès."),
            "appointment": AppointmentDetailSerializer(appointment).data,
        })


class StaffAppointmentRescheduleView(APIView):
    """
    PATCH /api/appointments/{id}/reschedule/
    Report d'un rendez-vous par le personnel médical (Secrétaire ou Médecin).
    Rappel : Secrétaire et Médecin peuvent UNIQUEMENT reporter (pas annuler).
    """
    permission_classes = [IsClinicStaff]

    def patch(self, request, pk):
        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return Response({"detail": _("Rendez-vous introuvable.")}, status=status.HTTP_404_NOT_FOUND)

        serializer = StaffRescheduleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_date = serializer.validated_data["new_date"]
        new_time = serializer.validated_data["new_time"]
        doctor_id = serializer.validated_data.get("doctor_id")

        try:
            with transaction.atomic():
                appointment.reschedule(new_date=new_date, new_time=new_time)
                if doctor_id:
                    doctor = User.objects.filter(pk=doctor_id, role=User.Role.DOCTOR).first()
                    if doctor:
                        appointment.doctor = doctor
                        appointment.save(update_fields=["doctor"])
        except DjangoValidationError as e:
            return Response({"detail": e.messages if hasattr(e, "messages") else str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": _("Rendez-vous reporté avec succès."),
            "appointment": AppointmentDetailSerializer(appointment).data,
        })


class DoctorAvailabilityListCreateView(generics.ListCreateAPIView):
    """
    GET /api/doctor/availabilities/ -> Liste des disponibilités du médecin connecté
    POST /api/doctor/availabilities/ -> Définition d'une nouvelle plage horaire
    """
    permission_classes = [IsDoctorUser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DoctorAvailabilityCreateSerializer
        return DoctorAvailabilitySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == User.Role.ADMIN:
            return DoctorAvailability.objects.all().select_related("doctor", "specialty")
        return DoctorAvailability.objects.filter(doctor=user).select_related("doctor", "specialty")

    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user)


class DoctorAvailabilityDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET / PUT / PATCH / DELETE /api/doctor/availabilities/{id}/
    Gestion d'une plage horaire de disponibilité spécifique.
    """
    permission_classes = [IsDoctorUser]
    serializer_class = DoctorAvailabilityCreateSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == User.Role.ADMIN:
            return DoctorAvailability.objects.all()
        return DoctorAvailability.objects.filter(doctor=user)
