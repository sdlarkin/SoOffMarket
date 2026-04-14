from django.test import TestCase
from properties.models import Property
from buyers.models import BuyBox, Buyer
from matcher.services import MatcherEngine

class MatcherEngineTests(TestCase):

    def setUp(self):
        # Establish Buyers
        self.talo = Buyer.objects.create(name="Talo", email="talo@test.com")
        self.jim = Buyer.objects.create(name="Jim", email="jim@test.com")
        self.craig = Buyer.objects.create(name="Craig", email="craig@test.com")

        # Establish BuyBoxes
        self.talo_box = BuyBox.objects.create(
            buyer=self.talo, 
            asset_type="RV Parks", 
            target_states="Colorado Florida Georgia North Carolina South Carolina"
        )
        self.jim_box = BuyBox.objects.create(
            buyer=self.jim, 
            asset_type="RV Parks", 
            target_states="Arizona Nevada New Mexico Texas"
        )
        self.craig_box = BuyBox.objects.create(
            buyer=self.craig, 
            asset_type="RV Parks", 
            target_states="Illinois Iowa Kansas Kentucky Maine Massachusetts Michigan"
        )

        # Establish Properties
        self.camp_outback = Property.objects.create(
            address="160 Himrich Dr", zip_code="97527", city="Grants Pass", state="OR", industry="Campgrounds", company_name="Camp Outback"
        )
        self.koa = Property.objects.create(
            address="123 Ark Lane", zip_code="72001", city="Little Rock", state="AR", industry="Campgrounds", company_name="Koa Kampgrounds"
        )
        self.woodhaven = Property.objects.create(
            address="509 La Moille", zip_code="61367", city="Sublette", state="IL", industry="Campgrounds", company_name="Woodhaven Lakes"
        )

    def test_false_positive_or_vs_florida(self):
        # Camp Outback is in OR. Talo wants Florida/Colorado/Carolina. 
        # State 'OR' matches substring in 'flORida' and 'colORado'. This should FAIL the match.
        result = MatcherEngine.evaluate_match(self.camp_outback, self.talo_box)
        self.assertFalse(result, "Engine falsely matched OR with Florida/Colorado")

    def test_false_positive_ar_vs_arizona(self):
        # Koa is in AR (Arkansas). Jim wants Arizona.
        # State 'AR' matches substring in 'ARizona'. This should FAIL the match.
        result = MatcherEngine.evaluate_match(self.koa, self.jim_box)
        self.assertFalse(result, "Engine falsely matched AR with Arizona")

    def test_false_positive_ar_vs_carolina(self):
        # Koa is in AR (Arkansas). Talo wants North Carolina.
        # State 'AR' matches substring in 'cARolina'. This should FAIL the match.
        result = MatcherEngine.evaluate_match(self.koa, self.talo_box)
        self.assertFalse(result, "Engine falsely matched AR with Carolina")

    def test_true_positive_illinois_exact(self):
        # Woodhaven is IL. Craig wants explicitly 'Illinois'.
        # This is a TRUE match.
        result = MatcherEngine.evaluate_match(self.woodhaven, self.craig_box)
        self.assertTrue(result, "Engine failed to match IL with Illinois")

    def test_true_positive_nationwide(self):
        # Any nationwide buyer should match any property.
        nationwide = BuyBox.objects.create(buyer=self.talo, asset_type="RV Parks", target_states="Nationwide")
        result = MatcherEngine.evaluate_match(self.camp_outback, nationwide)
        self.assertTrue(result, "Engine failed to process Nationwide wildcard")
