from django.contrib import admin
from .models import Buyer, BuyBox

@admin.register(Buyer)
class BuyerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'company_name', 'location', 'created_at')
    search_fields = ('name', 'email', 'company_name')

@admin.register(BuyBox)
class BuyBoxAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'asset_type', 'target_states', 'is_cash_buyer', 'created_at')
    list_filter = ('asset_type', 'is_cash_buyer', 'virtual_acquisitions')
    search_fields = ('buyer__name', 'buyer__email', 'target_states', 'asset_type')
