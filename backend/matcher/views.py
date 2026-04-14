from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from .models import PropertyMatch
from .serializers import PropertyMatchListSerializer, PropertyMatchDetailSerializer

class MatchPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class PropertyMatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PropertyMatch.objects.all().select_related(
        'property', 'buybox', 'buybox__buyer'
    ).order_by('-created_at')
    
    pagination_class = MatchPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return PropertyMatchListSerializer
        return PropertyMatchDetailSerializer

# --- NEW PROPERTY-CENTRIC VIEW SET ---
from django.db.models import Count
from properties.models import Property
from .serializers import MatchedPropertyListSerializer, MatchedPropertyDetailSerializer

class MatchedPropertiesViewSet(viewsets.ReadOnlyModelViewSet):
    # Filter only properties that have at least one match, annotate with the total count
    queryset = Property.objects.filter(buyer_matches__isnull=False).distinct().annotate(
        match_count=Count('buyer_matches')
    ).order_by('-match_count', 'company_name')
    
    pagination_class = MatchPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return MatchedPropertyListSerializer
        return MatchedPropertyDetailSerializer
