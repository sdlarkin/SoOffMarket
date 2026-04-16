from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Parcel, ParcelRating
from .serializers import (
    ParcelListSerializer,
    ParcelOverviewSerializer,
    ParcelDetailSerializer,
    ParcelRatingSerializer,
)


class ParcelPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ParcelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Parcel.objects.filter(is_target=True).select_related('rating', 'owner')
    pagination_class = ParcelPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ParcelListSerializer
        if self.action == 'overview':
            return ParcelOverviewSerializer
        return ParcelDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        rating = params.get('rating')
        if rating:
            if rating == 'unrated':
                qs = qs.filter(rating__isnull=True)
            else:
                qs = qs.filter(rating__rating=rating)

        tier = params.get('tier')
        if tier:
            qs = qs.filter(deal_tier=tier)

        grade = params.get('grade')
        if grade:
            qs = qs.filter(duplex_friendliness=grade)

        geo = params.get('geo')
        if geo:
            qs = qs.filter(geo_priority__icontains=geo)

        return qs

    @action(detail=False, methods=['get'])
    def overview(self, request):
        qs = self.get_queryset()
        serializer = ParcelOverviewSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def rate(self, request, pk=None):
        parcel = self.get_object()
        rating_obj, _ = ParcelRating.objects.get_or_create(parcel=parcel)
        serializer = ParcelRatingSerializer(rating_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Bulk update sort_order for parcels. Expects: { "order": ["uuid1", "uuid2", ...] }"""
        order = request.data.get('order', [])
        for i, parcel_id in enumerate(order):
            ParcelRating.objects.filter(parcel_id=parcel_id).update(sort_order=i)
        return Response({'updated': len(order)})
