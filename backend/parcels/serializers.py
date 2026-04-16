from rest_framework import serializers
from .models import Parcel, CompParcel, ParcelRating, Owner


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = [
            'id', 'name', 'first_name', 'last_name', 'mailing_address',
            'phone_1', 'phone_1_type', 'phone_2', 'phone_2_type',
            'phone_3', 'phone_3_type',
            'email_1', 'email_2', 'email_3',
            'age', 'skip_traced', 'skip_trace_date',
        ]


class ParcelRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParcelRating
        fields = ['rating', 'sort_order', 'notes', 'updated_at']


class ParcelOverviewSerializer(serializers.ModelSerializer):
    rating = serializers.CharField(source='rating.rating', read_only=True, default='')
    sort_order = serializers.IntegerField(source='rating.sort_order', read_only=True, default=0)

    class Meta:
        model = Parcel
        fields = [
            'id', 'parcel_id', 'lat', 'lon', 'deal_tier',
            'duplex_friendliness', 'geo_priority', 'address',
            'calc_acres', 'computed_acres', 'appraised_value',
            'land_est_value', 'arv_comp_median', 'rating', 'sort_order',
            'owner_adjacent', 'owner_lives_adjacent',
        ]


class ParcelListSerializer(serializers.ModelSerializer):
    rating = ParcelRatingSerializer(read_only=True)

    class Meta:
        model = Parcel
        fields = [
            'id', 'parcel_id', 'address', 'owner_name',
            'calc_acres', 'computed_acres', 'compactness',
            'appraised_value', 'land_value',
            'deal_tier', 'geo_priority',
            'duplex_friendliness', 'duplex_ratio',
            'land_est_value', 'arv_comp_median',
            'water_provider', 'sewer_provider', 'utilities_score',
            'lat', 'lon', 'assessor_link',
            'rating',
        ]


class CompParcelSerializer(serializers.ModelSerializer):
    comp_parcel_id = serializers.CharField(source='comp.parcel_id', read_only=True)
    comp_address = serializers.CharField(source='comp.address', read_only=True)
    comp_acres = serializers.FloatField(source='comp.calc_acres', read_only=True)

    class Meta:
        model = CompParcel
        fields = [
            'comp_type', 'comp_parcel_id', 'comp_address', 'comp_acres',
            'distance_ft', 'sale_price', 'sale_date',
        ]


class ParcelDetailSerializer(serializers.ModelSerializer):
    rating = ParcelRatingSerializer(read_only=True)
    comps = CompParcelSerializer(many=True, read_only=True)
    owner_detail = OwnerSerializer(source='owner', read_only=True)

    class Meta:
        model = Parcel
        fields = '__all__'
