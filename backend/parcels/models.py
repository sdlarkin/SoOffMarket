from django.db import models
import uuid


class Owner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Owner name as it appears on county records")
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    mailing_address = models.CharField(max_length=500, blank=True)

    # Skip trace results
    phone_1 = models.CharField(max_length=50, blank=True)
    phone_1_type = models.CharField(max_length=20, blank=True, help_text="Landline/Wireless/VoIP")
    phone_2 = models.CharField(max_length=50, blank=True)
    phone_2_type = models.CharField(max_length=20, blank=True)
    phone_3 = models.CharField(max_length=50, blank=True)
    phone_3_type = models.CharField(max_length=20, blank=True)
    email_1 = models.EmailField(blank=True)
    email_2 = models.EmailField(blank=True)
    email_3 = models.EmailField(blank=True)

    # Metadata from skip trace
    age = models.CharField(max_length=10, blank=True)
    skip_traced = models.BooleanField(default=False)
    skip_trace_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Owners"

    def __str__(self):
        return f"{self.name} ({self.phone_1 or 'no phone'})"


class Parcel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel_id = models.CharField(max_length=50, unique=True, help_text="Tax map number e.g. '155P H 001'")

    # Location
    address = models.CharField(max_length=255, blank=True)
    county = models.CharField(max_length=100, default="Hamilton")
    state = models.CharField(max_length=10, default="TN")

    # Owner
    owner = models.ForeignKey(Owner, null=True, blank=True, on_delete=models.SET_NULL, related_name='parcels')
    owner_name = models.CharField(max_length=255, blank=True)
    owner_name_2 = models.CharField(max_length=255, blank=True)
    owner_mailing = models.CharField(max_length=500, blank=True)

    # Acreage
    calc_acres = models.FloatField(null=True, blank=True, help_text="GIS-reported acreage")
    computed_acres = models.FloatField(null=True, blank=True, help_text="Computed from polygon geometry")
    compactness = models.FloatField(null=True, blank=True, help_text="Shape compactness score 0-1")

    # Values
    land_value = models.IntegerField(default=0)
    building_value = models.IntegerField(default=0)
    appraised_value = models.IntegerField(default=0)
    assessed_value = models.IntegerField(default=0)

    # Classification
    zoning = models.CharField(max_length=20, blank=True, default="R-2")
    land_use_code = models.CharField(max_length=20, blank=True)
    district = models.CharField(max_length=20, blank=True)

    # Utilities
    water_provider = models.CharField(max_length=255, blank=True)
    sewer_provider = models.CharField(max_length=255, blank=True)
    utilities_score = models.CharField(max_length=50, blank=True)

    # Geography
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    geometry_rings = models.JSONField(default=list, blank=True, help_text="Polygon rings as [[lat,lon],...] for Leaflet")

    # Last sale
    last_sale_date = models.CharField(max_length=50, blank=True)
    last_sale_price = models.IntegerField(default=0)

    # Links
    assessor_link = models.URLField(max_length=500, blank=True)

    # Comp analysis results (populated for target parcels)
    land_comp_count = models.IntegerField(default=0)
    land_comp_radius = models.CharField(max_length=50, blank=True)
    land_comp_min = models.IntegerField(null=True, blank=True)
    land_comp_max = models.IntegerField(null=True, blank=True)
    land_comp_median = models.FloatField(null=True, blank=True)
    land_comp_avg_ppa = models.FloatField(null=True, blank=True)
    land_est_value = models.FloatField(null=True, blank=True)
    land_comp_details = models.TextField(blank=True)

    arv_comp_count = models.IntegerField(default=0)
    arv_comp_radius = models.CharField(max_length=50, blank=True)
    arv_comp_min = models.IntegerField(null=True, blank=True)
    arv_comp_max = models.IntegerField(null=True, blank=True)
    arv_comp_median = models.FloatField(null=True, blank=True)
    arv_comp_details = models.TextField(blank=True)

    # Duplex friendliness
    nearby_sfr = models.IntegerField(default=0)
    nearby_duplex = models.IntegerField(default=0)
    nearby_triplex = models.IntegerField(default=0)
    nearby_quad = models.IntegerField(default=0)
    nearby_total = models.IntegerField(default=0)
    duplex_ratio = models.FloatField(null=True, blank=True)
    duplex_friendliness = models.CharField(max_length=1, blank=True, help_text="A/B/C/D grade")

    # Deal classification
    deal_tier = models.CharField(max_length=10, blank=True)
    geo_priority = models.CharField(max_length=100, blank=True)

    # Link to buyer
    buybox = models.ForeignKey(
        'buyers.BuyBox', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='target_parcels'
    )

    # Adjacency analysis
    owner_adjacent = models.BooleanField(default=False, help_text="Owner has an adjacent parcel")
    owner_lives_adjacent = models.BooleanField(default=False, help_text="Owner has adjacent parcel with a building (lives next door)")
    adjacent_details = models.TextField(blank=True, help_text="Details of adjacent same-owner parcels")

    is_target = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['geo_priority', 'duplex_friendliness', 'parcel_id']
        verbose_name_plural = "Parcels"

    def __str__(self):
        return f"{self.parcel_id} - {self.address or 'No address'}"


class CompParcel(models.Model):
    COMP_TYPES = [('land', 'Land Comp'), ('arv', 'ARV Comp')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='comps')
    comp = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='comp_for')
    comp_type = models.CharField(max_length=10, choices=COMP_TYPES)
    distance_ft = models.FloatField(null=True, blank=True)
    sale_price = models.IntegerField(null=True, blank=True)
    sale_date = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('target', 'comp', 'comp_type')
        verbose_name_plural = "Comp Parcels"

    def __str__(self):
        return f"{self.comp_type} comp: {self.comp.parcel_id} for {self.target.parcel_id}"


class ParcelRating(models.Model):
    RATING_CHOICES = [
        ('yes', 'Yes'),
        ('maybe', 'Maybe'),
        ('no', 'No'),
        ('skip', 'Skip'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel = models.OneToOneField(Parcel, on_delete=models.CASCADE, related_name='rating')
    rating = models.CharField(max_length=10, choices=RATING_CHOICES, blank=True)
    sort_order = models.IntegerField(default=0, help_text="Manual sort order within rating category (lower = higher priority)")
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.parcel.parcel_id}: {self.rating}"
