from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ParcelViewSet,
    deals_index, deals_buyer, deals_buybox_overview, deals_parcel_detail,
)

router = DefaultRouter()
router.register(r'parcels', ParcelViewSet, basename='parcel')

urlpatterns = [
    path('', include(router.urls)),

    # Deals API: public-facing endpoints by buyer/buybox slug
    path('deals/', deals_index, name='deals-index'),
    path('deals/<slug:buyer_slug>/', deals_buyer, name='deals-buyer'),
    path('deals/<slug:buyer_slug>/<slug:buybox_slug>/', deals_buybox_overview, name='deals-buybox'),
    path('deals/<slug:buyer_slug>/<slug:buybox_slug>/<uuid:parcel_id>/', deals_parcel_detail, name='deals-parcel-detail'),
]
