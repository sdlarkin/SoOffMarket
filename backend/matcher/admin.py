from django.contrib import admin
from .models import PropertyMatch

@admin.register(PropertyMatch)
class PropertyMatchAdmin(admin.ModelAdmin):
    list_display = ('property', 'get_buyer_name', 'get_asset_type', 'match_score', 'created_at')
    search_fields = ('property__company_name', 'buybox__buyer__name', 'buybox__asset_type')
    
    def get_buyer_name(self, obj):
        return obj.buybox.buyer.name
    get_buyer_name.short_description = 'Buyer'
    get_buyer_name.admin_order_field = 'buybox__buyer__name'

    def get_asset_type(self, obj):
        return obj.buybox.asset_type
    get_asset_type.short_description = 'BuyBox Asset Type'
