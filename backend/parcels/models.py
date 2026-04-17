from django.db import models
import uuid


class County(models.Model):
    """GIS configuration for a county. Stores ArcGIS layer URLs, field mappings,
    and county-specific parameters so the pipeline works for any county."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    state = models.CharField(max_length=10)
    slug = models.SlugField(max_length=100, unique=True)
    fips = models.CharField(max_length=10, blank=True, help_text="FIPS county code")

    # GIS Layer URLs
    parcel_layer_url = models.URLField(max_length=500, help_text="ArcGIS REST parcel layer URL")
    parcel_layer_wkid = models.IntegerField(default=6576, help_text="Spatial reference WKID for parcel layer")
    zoning_layer_url = models.URLField(max_length=500, blank=True, help_text="ArcGIS REST zoning layer URL")
    zoning_layer_wkid = models.IntegerField(default=2274, help_text="Spatial reference WKID for zoning layer")
    zoning_zone_field = models.CharField(max_length=50, default="ZONE", help_text="Field name for zone designation")
    water_layer_url = models.URLField(max_length=500, blank=True)
    water_layer_provider_field = models.CharField(max_length=50, default="DISTRICT", blank=True)
    sewer_layer_url = models.URLField(max_length=500, blank=True)
    sewer_layer_provider_field = models.CharField(max_length=50, default="ServiceProvider", blank=True)

    # Field mapping: canonical name -> county-specific GIS field name
    field_map = models.JSONField(default=dict, help_text="Maps canonical names to GIS field names: {parcel_id: TAX_MAP_NO, address: ADDRESS, ...}")

    # County-specific entity exclusion keywords (in addition to universal ones)
    entity_keywords = models.JSONField(default=list, blank=True, help_text="County-specific entity keywords e.g. ['CHATT CITY', 'HAMILTON COUNTY']")

    # Coordinate conversion
    out_sr = models.IntegerField(default=4326, help_text="Output spatial reference for lat/lon (usually WGS84 = 4326)")

    # Market rules: state/county-specific rules that affect deal analysis
    market_rules = models.JSONField(default=dict, blank=True, help_text=(
        "State/county-specific rules. Keys:\n"
        "  prop_13: bool — CA Prop 13 frozen assessments\n"
        "  assessment_reflects_market: bool — whether assessed value tracks market value\n"
        "  reassessment_frequency: str — 'annual', 'biennial', 'on_sale', etc.\n"
        "  homestead_exempt: bool — FL/TX homestead exemption affects analysis\n"
        "  transfer_tax_rate: float — documentary stamp / transfer tax %\n"
        "  disclosure_state: bool — seller must disclose defects\n"
        "  comp_strategy: str — 'land_arv' (vacant land), 'acquisition_arv' (fix-flip), 'single'\n"
        "  flip_indicators: list — which fields indicate distress in this market\n"
        "  notes: str — free-form notes about this market"
    ))

    # Metadata
    max_records_per_query = models.IntegerField(default=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Counties"
        unique_together = ('name', 'state')

    def __str__(self):
        return f"{self.name}, {self.state}"


class MarketSnapshot(models.Model):
    """Cached county-wide market statistics. Computed from GIS data, refreshed periodically.
    Avoids re-computing medians and benchmarks on every pipeline run."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='snapshots')

    # When this snapshot was computed
    computed_at = models.DateTimeField(auto_now_add=True)
    parcel_count = models.IntegerField(default=0, help_text="Total parcels queried")

    # County-wide stats
    median_total_value = models.IntegerField(null=True, blank=True)
    median_ppsf = models.FloatField(null=True, blank=True, help_text="Median price per sqft")
    median_land_value = models.IntegerField(null=True, blank=True)
    median_impr_ratio = models.FloatField(null=True, blank=True)
    ppa_floor = models.FloatField(null=True, blank=True, help_text="25th percentile $/acre for land comps")
    ppa_cap = models.FloatField(null=True, blank=True, help_text="3x median $/acre for land comps")

    # Community-level stats stored as JSON: {community_name: {median_total, median_ppsf, p75_total, count}}
    community_stats = models.JSONField(default=dict, blank=True)

    # Flip analysis data (for fix-flip markets)
    flip_rate = models.FloatField(null=True, blank=True, help_text="% of recent sales that are likely flips")
    flip_non_owner_occ_rate = models.FloatField(null=True, blank=True)
    flip_median_ppsf = models.FloatField(null=True, blank=True)

    # Year-over-year trends stored as JSON: {year: {flip_pct, median_total, ...}}
    yearly_trends = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-computed_at']
        get_latest_by = 'computed_at'

    def __str__(self):
        return f"{self.county} snapshot ({self.computed_at.strftime('%Y-%m-%d')})"

    @property
    def is_stale(self):
        """Consider stale after 30 days."""
        from django.utils import timezone
        from datetime import timedelta
        return (timezone.now() - self.computed_at) > timedelta(days=30)


class GISParcelCache(models.Model):
    """Cached raw parcel data from GIS queries. Avoids re-querying the same
    county's GIS on every pipeline run. Keyed by APN/parcel_id."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='parcel_cache')
    parcel_id = models.CharField(max_length=50, help_text="APN or tax map number")

    # Raw GIS data stored as JSON (all fields from the GIS query)
    raw_data = models.JSONField(default=dict)

    # Parsed/computed fields for fast querying
    address = models.CharField(max_length=255, blank=True, db_index=True)
    community = models.CharField(max_length=100, blank=True, db_index=True)
    total_value = models.IntegerField(null=True, blank=True, db_index=True)
    land_value = models.IntegerField(null=True, blank=True)
    impr_value = models.IntegerField(null=True, blank=True)
    sqft = models.IntegerField(null=True, blank=True)
    bedrooms = models.IntegerField(null=True, blank=True)
    year_built = models.IntegerField(null=True, blank=True)
    acreage = models.FloatField(null=True, blank=True)
    owner_occupied = models.BooleanField(null=True, blank=True, db_index=True)
    sale_year = models.IntegerField(null=True, blank=True, db_index=True)
    land_use_code = models.CharField(max_length=10, blank=True, db_index=True)

    # Geometry
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    geometry_rings = models.JSONField(default=list, blank=True)

    # Metadata
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('county', 'parcel_id')
        indexes = [
            models.Index(fields=['county', 'land_use_code', 'total_value']),
            models.Index(fields=['county', 'community', 'total_value']),
            models.Index(fields=['county', 'sale_year']),
        ]

    def __str__(self):
        return f"{self.parcel_id} ({self.county})"

    @property
    def impr_ratio(self):
        if self.total_value and self.total_value > 0:
            return (self.impr_value or 0) / self.total_value
        return None

    @property
    def ppsf(self):
        if self.sqft and self.sqft > 0 and self.total_value:
            return self.total_value / self.sqft
        return None


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
