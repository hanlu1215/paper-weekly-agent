from django.urls import path

from publisher.views import health, publish

urlpatterns = [
    path("", health),
    path("api/publish", publish),
]
