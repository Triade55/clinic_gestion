from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.EncaissementCreateView.as_view(), name="encaissement"),
    path("patients/search/", views.PatientSearchView.as_view(), name="patient_search"),
    path("invoices/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/pay/", views.InvoicePaymentCreateView.as_view(), name="invoice_pay"),
    path("payments/<int:pk>/receipt/", views.PaymentReceiptView.as_view(), name="payment_receipt"),
]
