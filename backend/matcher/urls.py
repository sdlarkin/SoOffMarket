from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyMatchViewSet, MatchedPropertiesViewSet

router = DefaultRouter()
router.register(r'matches', PropertyMatchViewSet, basename='match')
router.register(r'matched-properties', MatchedPropertiesViewSet, basename='matched-properties')

urlpatterns = [
    path('', include(router.urls)),
]
