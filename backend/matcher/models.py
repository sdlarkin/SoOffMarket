from django.db import models
import uuid

# Delay importing if necessary or just import directly
from buyers.models import BuyBox
from properties.models import Property

class PropertyMatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='buyer_matches')
    buybox = models.ForeignKey(BuyBox, on_delete=models.CASCADE, related_name='property_matches')
    
    match_score = models.FloatField(default=100.0)
    match_reason = models.TextField(blank=True, help_text="Why did this match?")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Property Matches"
        unique_together = ('property', 'buybox')

    def __str__(self):
        return f"Match: {self.buybox.buyer.name} <-> {self.property.company_name}"
