from django.urls import path
from . import views

app_name = "appointments"

urlpatterns = [
    # --- ENDPOINTS PUBLICS (PATIENT) ---
    path("api/public/specialties/", views.PublicSpecialtyListView.as_view(), name="public_specialties"),
    path("api/public/slots/", views.PublicAvailableSlotsView.as_view(), name="public_slots"),
    path("api/public/appointments/", views.PublicAppointmentCreateView.as_view(), name="public_appointment_create"),
    path("api/public/appointments/lookup/", views.PublicAppointmentLookupView.as_view(), name="public_appointment_lookup"),
    path("api/public/appointments/reschedule/", views.PublicAppointmentRescheduleView.as_view(), name="public_appointment_reschedule"),
    path("api/public/appointments/cancel/", views.PublicAppointmentCancelView.as_view(), name="public_appointment_cancel"),

    # --- ENDPOINTS INTERNES (PERSONNEL CLINIQUE) ---
    path("api/appointments/", views.StaffAppointmentListView.as_view(), name="staff_appointment_list"),
    path("api/appointments/<int:pk>/", views.StaffAppointmentDetailView.as_view(), name="staff_appointment_detail"),
    path("api/appointments/<int:pk>/confirm/", views.StaffAppointmentConfirmView.as_view(), name="staff_appointment_confirm"),
    path("api/appointments/<int:pk>/checkin/", views.StaffAppointmentCheckinView.as_view(), name="staff_appointment_checkin"),
    path("api/appointments/<int:pk>/start/", views.StaffAppointmentStartConsultationView.as_view(), name="staff_appointment_start"),
    path("api/appointments/<int:pk>/finish/", views.StaffAppointmentFinishConsultationView.as_view(), name="staff_appointment_finish"),
    path("api/appointments/<int:pk>/reschedule/", views.StaffAppointmentRescheduleView.as_view(), name="staff_appointment_reschedule"),

    # --- DISPONIBILITÉS MÉDECINS ---
    path("api/doctor/availabilities/", views.DoctorAvailabilityListCreateView.as_view(), name="doctor_availabilities"),
    path("api/doctor/availabilities/<int:pk>/", views.DoctorAvailabilityDetailView.as_view(), name="doctor_availability_detail"),
]
