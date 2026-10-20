from django.contrib import admin
from .models import Appointment, DoctorAvailability


@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("doctor", "specialty", "day_of_week", "start_time", "end_time", "slot_duration_minutes", "is_active")
    list_filter = ("day_of_week", "specialty", "is_active")
    search_fields = ("doctor__first_name", "doctor__last_name", "doctor__email", "specialty__name")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "booking_reference",
        "last_name",
        "first_name",
        "phone_number",
        "specialty",
        "doctor",
        "appointment_date",
        "appointment_time",
        "status",
    )
    list_filter = ("status", "specialty", "appointment_date")
    search_fields = ("booking_reference", "last_name", "first_name", "phone_number", "patient__patient_number")
    readonly_fields = ("booking_reference", "created_at", "updated_at", "rescheduled_count")
