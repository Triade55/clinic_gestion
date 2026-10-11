from django.contrib import admin
from .models import Invoice, Patient, Specialty


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    list_editable = ("price", "is_active")


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("patient_number", "last_name", "first_name", "phone_number", "created_at")
    search_fields = ("patient_number", "last_name", "first_name", "phone_number")
    readonly_fields = ("patient_number", "created_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "patient",
        "specialty",
        "consultation_fee",
        "amount_received",
        "amount_change",
        "amount_remaining",
        "payment_status",
        "created_by",
        "created_at",
    )
    list_filter = ("payment_status", "specialty", "created_at")
    search_fields = ("invoice_number", "patient__patient_number", "patient__last_name", "patient__first_name")
    readonly_fields = ("invoice_number", "amount_change", "amount_remaining", "payment_status", "created_at")
