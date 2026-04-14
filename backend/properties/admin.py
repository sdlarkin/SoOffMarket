from django.contrib import admin
from .models import Property, Contact

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'address', 'city', 'state', 'industry', 'created_at')
    list_filter = ('state', 'industry')
    search_fields = ('company_name', 'address', 'city', 'zip_code', 'main_phone')

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'title', 'property', 'email', 'direct_phone')
    list_filter = ('property__state', 'title')
    search_fields = ('first_name', 'last_name', 'email', 'property__company_name')
