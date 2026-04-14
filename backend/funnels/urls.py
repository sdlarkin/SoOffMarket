from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FunnelViewSet, LeadViewSet

router = DefaultRouter()
router.register(r'funnels', FunnelViewSet)
router.register(r'leads', LeadViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
