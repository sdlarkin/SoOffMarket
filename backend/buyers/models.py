from django.db import models
from django.utils.text import slugify
import uuid

class Buyer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    blinq_or_website = models.URLField(max_length=500, blank=True)
    location = models.CharField(max_length=255, blank=True, help_text="Where are you located?")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.company_name})"

class BuyBox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name='buy_boxes')
    slug = models.SlugField(max_length=100, blank=True)

    asset_type = models.CharField(max_length=255, help_text="Primary Asset Class (Derived from Sheet Tab)")
    
    target_states = models.TextField(help_text="Comma-separated list of states they are buying in")
    area_preference = models.CharField(max_length=255, help_text="Metro, suburban, or rural areas?")
    virtual_acquisitions = models.CharField(max_length=50, help_text="Are you open to virtual acquisitions? (Yes/No)")
    
    property_types = models.TextField(help_text="What type of properties do you buy? (Stored as a list)")
    price_range = models.CharField(max_length=255, help_text="What is your ideal purchase price range?")
    
    is_cash_buyer = models.CharField(max_length=50, help_text="Are you a cash buyer?")
    deal_structures = models.TextField(help_text="All Cash, Subject-To, Seller Finance, etc.")
    equity_arv_requirement = models.TextField(help_text="Do you require a specific equity spread or ARV percentage?")
    
    property_condition = models.TextField(help_text="What level of property condition are you open to purchasing?")
    cheat_codes = models.CharField(max_length=255, blank=True, help_text="Cheat Codes")
    strategy_notes = models.TextField(blank=True, help_text="Anything else we should know about your buy box or investment strategy?")

    # Pipeline parameters (used by execution scripts)
    county = models.ForeignKey(
        'parcels.County', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='buyboxes',
        help_text="County this buybox targets (links to GIS config)"
    )
    target_zoning = models.JSONField(default=list, blank=True, help_text='Zoning codes to match, e.g. ["R-2"]')
    min_acres = models.FloatField(null=True, blank=True, help_text="Minimum acreage filter")
    max_acres = models.FloatField(null=True, blank=True, help_text="Maximum acreage filter (null = no max)")
    max_price = models.IntegerField(null=True, blank=True, help_text="Maximum appraised value filter")
    target_geography = models.JSONField(default=dict, blank=True, help_text='Geography filters: {target_districts: [...], exclude_districts: [...], mixed_districts: {...}}')
    min_compactness = models.FloatField(default=0.25, help_text="Minimum lot compactness score (0-1)")
    comp_search_tiers = models.JSONField(default=list, blank=True, help_text='Comp search tiers: [{radius_ft, lookback_months, label}]')
    duplex_scoring_enabled = models.BooleanField(default=True, help_text="Whether to run duplex friendliness scoring")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('buyer', 'slug')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.asset_type[:80])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset_type} BuyBox for {self.buyer.name}"
