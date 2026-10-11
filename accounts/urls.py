from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.ClinicLoginView.as_view(), name="login"),
    path("logout/", views.ClinicLogoutView.as_view(), name="logout"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("password-change/", views.ClinicPasswordChangeView.as_view(), name="password_change"),
    path("password-change/done/", views.ClinicPasswordChangeDoneView.as_view(), name="password_change_done"),
    path("password-reset/", views.ClinicPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", views.ClinicPasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.ClinicPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.ClinicPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
