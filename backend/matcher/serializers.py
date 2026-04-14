from rest_framework import serializers
from properties.models import Property, Contact
from buyers.models import Buyer, BuyBox
from .models import PropertyMatch

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'

class PropertySerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(many=True, read_only=True)
    class Meta:
        model = Property
        fields = '__all__'

class BuyerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Buyer
        fields = '__all__'

class BuyBoxSerializer(serializers.ModelSerializer):
    buyer = BuyerSerializer(read_only=True)
    class Meta:
        model = BuyBox
        fields = '__all__'

class PropertyMatchListSerializer(serializers.ModelSerializer):
    # Minimal details for the paginated list view
    property_name = serializers.CharField(source='property.company_name', read_only=True)
    property_state = serializers.CharField(source='property.state', read_only=True)
    buyer_name = serializers.CharField(source='buybox.buyer.name', read_only=True)
    asset_type = serializers.CharField(source='buybox.asset_type', read_only=True)
    
    class Meta:
        model = PropertyMatch
        fields = ['id', 'property_name', 'property_state', 'buyer_name', 'asset_type', 'match_score', 'match_reason', 'created_at']

class PropertyMatchDetailSerializer(serializers.ModelSerializer):
    # Deep nested details for the detail side-by-side page
    property = PropertySerializer(read_only=True)
    buybox = BuyBoxSerializer(read_only=True)

    class Meta:
        model = PropertyMatch
        fields = '__all__'

# --- NEW PROPERTY-CENTRIC SERIALIZERS ---
class EmbeddedMatchSerializer(serializers.ModelSerializer):
    # Embedded explicitly inside the MatchedProperty detail view
    buybox = BuyBoxSerializer(read_only=True)
    
    class Meta:
        model = PropertyMatch
        fields = ['id', 'buybox', 'match_score', 'match_reason', 'created_at']

class MatchedPropertyDetailSerializer(serializers.ModelSerializer):
    # Full deep response for /properties-matched/[id]/
    contacts = ContactSerializer(many=True, read_only=True)
    buyer_matches = EmbeddedMatchSerializer(many=True, read_only=True)
    match_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Property
        fields = '__all__'

class MatchedPropertyListSerializer(serializers.ModelSerializer):
    # Lightweight list response
    match_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Property
        fields = ['id', 'company_name', 'address', 'city', 'state', 'zip_code', 'industry', 'match_count']
