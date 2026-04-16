from rest_framework import viewsets, serializers as drf_serializers
from rest_framework.decorators import action, api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from buyers.models import Buyer, BuyBox
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


# ── Deals API: public-facing endpoints by buyer/buybox slug ──

class BuyBoxSummarySerializer(drf_serializers.ModelSerializer):
    parcel_count = drf_serializers.IntegerField(read_only=True)
    buyer_name = drf_serializers.CharField(source='buyer.name', read_only=True)
    buyer_slug = drf_serializers.CharField(source='buyer.slug', read_only=True)

    class Meta:
        model = BuyBox
        fields = ['id', 'slug', 'asset_type', 'target_states', 'price_range',
                  'buyer_name', 'buyer_slug', 'parcel_count']


class BuyerSummarySerializer(drf_serializers.ModelSerializer):
    buybox_count = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = Buyer
        fields = ['id', 'name', 'slug', 'company_name', 'buybox_count']


@api_view(['GET'])
def deals_index(request):
    """List all buyers that have active deal searches."""
    from django.db.models import Count
    buyers = Buyer.objects.annotate(
        buybox_count=Count('buy_boxes__target_parcels', distinct=True)
    ).filter(buybox_count__gt=0)
    serializer = BuyerSummarySerializer(buyers, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def deals_buyer(request, buyer_slug):
    """List all buyboxes for a buyer."""
    from django.db.models import Count
    buyer = get_object_or_404(Buyer, slug=buyer_slug)
    buyboxes = buyer.buy_boxes.annotate(
        parcel_count=Count('target_parcels')
    ).filter(parcel_count__gt=0)
    serializer = BuyBoxSummarySerializer(buyboxes, many=True)
    return Response({
        'buyer': {'name': buyer.name, 'slug': buyer.slug, 'company_name': buyer.company_name},
        'buyboxes': serializer.data,
    })


@api_view(['GET'])
def deals_buybox_overview(request, buyer_slug, buybox_slug):
    """Get all parcels for a specific buybox (overview for map)."""
    buyer = get_object_or_404(Buyer, slug=buyer_slug)
    buybox = get_object_or_404(BuyBox, buyer=buyer, slug=buybox_slug)
    parcels = Parcel.objects.filter(
        buybox=buybox, is_target=True
    ).select_related('rating')

    # Apply filters from query params
    rating = request.query_params.get('rating')
    if rating:
        if rating == 'unrated':
            parcels = parcels.filter(rating__isnull=True)
        else:
            parcels = parcels.filter(rating__rating=rating)

    serializer = ParcelOverviewSerializer(parcels, many=True)
    return Response({
        'buyer': {'name': buyer.name, 'slug': buyer.slug},
        'buybox': {'slug': buybox.slug, 'asset_type': buybox.asset_type, 'target_states': buybox.target_states, 'price_range': buybox.price_range},
        'parcels': serializer.data,
    })


@api_view(['GET'])
def deals_parcel_detail(request, buyer_slug, buybox_slug, parcel_id):
    """Get full parcel detail within a buybox context."""
    buyer = get_object_or_404(Buyer, slug=buyer_slug)
    buybox = get_object_or_404(BuyBox, buyer=buyer, slug=buybox_slug)
    parcel = get_object_or_404(Parcel, id=parcel_id, buybox=buybox, is_target=True)
    serializer = ParcelDetailSerializer(parcel)
    return Response(serializer.data)
