from django.contrib import admin
from .models import Parcel, CompParcel, ParcelRating, Owner, County, MarketSnapshot, GISParcelCache


@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    list_display = ['name', 'state', 'slug', 'parcel_layer_url', 'updated_at']
    search_fields = ['name', 'state']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(MarketSnapshot)
class MarketSnapshotAdmin(admin.ModelAdmin):
    list_display = ['county', 'computed_at', 'parcel_count', 'median_total_value', 'median_ppsf', 'flip_rate']
    list_filter = ['county']
    readonly_fields = ['computed_at']


@admin.register(GISParcelCache)
class GISParcelCacheAdmin(admin.ModelAdmin):
    list_display = ['parcel_id', 'county', 'address', 'community', 'total_value', 'sqft', 'sale_year', 'owner_occupied']
    list_filter = ['county', 'community', 'owner_occupied']
    search_fields = ['parcel_id', 'address']


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone_1', 'phone_1_type', 'email_1', 'skip_traced']
    search_fields = ['name', 'first_name', 'last_name', 'phone_1', 'email_1']
    list_filter = ['skip_traced', 'phone_1_type']


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = [
        'parcel_id', 'address', 'computed_acres', 'appraised_value',
        'deal_tier', 'duplex_friendliness', 'geo_priority', 'is_target',
    ]
    list_filter = ['is_target', 'deal_tier', 'duplex_friendliness', 'geo_priority', 'district']
    search_fields = ['parcel_id', 'address', 'owner_name']


@admin.register(CompParcel)
class CompParcelAdmin(admin.ModelAdmin):
    list_display = ['target', 'comp', 'comp_type', 'sale_price', 'sale_date']
    list_filter = ['comp_type']


@admin.register(ParcelRating)
class ParcelRatingAdmin(admin.ModelAdmin):
    list_display = ['parcel', 'rating', 'updated_at']
    list_filter = ['rating']
