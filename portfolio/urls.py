from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/stocks/", views.stocks_api_dispatch, name="stocks_api"),
    path("api/optimize/", views.optimize_api, name="optimize_api"),
    path("api/optimize/<uuid:job_id>/", views.optimization_status_api, name="optimization_status_api"),
]
