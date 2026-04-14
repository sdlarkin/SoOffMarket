from django.db import models
import uuid

class Property(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Location used for Deduplication
    address = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=20)
    county = models.CharField(max_length=100, blank=True)
    
    # Company info
    company_name = models.CharField(max_length=255)
    main_phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(max_length=500, blank=True)
    
    # Asset Details
    employee_range = models.CharField(max_length=100, blank=True)
    annual_sales = models.CharField(max_length=100, blank=True)
    sic_code = models.CharField(max_length=50, blank=True)
    industry = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Properties"
        # Prevent creating multiple properties with the exact same address + zip combination
        unique_together = ('address', 'zip_code')

    def __str__(self):
        return f"{self.company_name} - {self.address}"

class Contact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='contacts')
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    title = models.CharField(max_length=150, blank=True)
    
    direct_phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True, max_length=255)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.title})"
