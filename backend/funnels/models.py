from django.db import models
import uuid

class Funnel(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class LandingPageContent(models.Model):
    funnel = models.OneToOneField(Funnel, on_delete=models.CASCADE, related_name='landing_page')
    hero_hook_frustration = models.TextField(help_text="Frustration-based hook template")
    hero_hook_results = models.TextField(help_text="Results-based hook template")
    hero_subheading = models.TextField()
    cta_text = models.CharField(max_length=100, default="Start the quiz")
    cta_microcopy = models.CharField(max_length=255, blank=True)
    
    value_prop_area_1 = models.CharField(max_length=255)
    value_prop_area_2 = models.CharField(max_length=255)
    value_prop_area_3 = models.CharField(max_length=255)
    
    bio_name = models.CharField(max_length=255, blank=True)
    bio_role = models.CharField(max_length=255, blank=True)
    bio_text = models.TextField(blank=True)
    research_text = models.TextField(blank=True)
    stats_json = models.JSONField(default=list, blank=True, help_text="List of statistics/research statements")

    def __str__(self):
        return f"Landing Content for {self.funnel.name}"

class Question(models.Model):
    TYPES = (
        ('BEST_PRACTICE', 'Best Practice (0-100 score)'),
        ('BIG_FIVE', 'Big Five (Qualification)'),
    )
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    type = models.CharField(max_length=20, choices=TYPES)
    order = models.PositiveIntegerField(default=0)
    weight = models.FloatField(default=1.0, help_text="Weight for scoring (only for BEST_PRACTICE)")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.get_type_display()}: {self.text[:50]}"

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    value = models.FloatField(default=0, help_text="Points awarded for this choice")

    def __str__(self):
        return self.text

class Lead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='leads')
    first_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=255, blank=True)
    
    score = models.FloatField(null=True, blank=True)
    tier_label = models.CharField(max_length=50, blank=True)
    next_step_type = models.CharField(max_length=50, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} ({self.email})"

class Answer(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)
    text_value = models.TextField(blank=True)

    def __str__(self):
        return f"Answer to {self.question.id} by {self.lead.id}"

class ResultTier(models.Model):
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='tiers')
    min_score = models.FloatField()
    max_score = models.FloatField()
    label = models.CharField(max_length=50) # Cold/Warm/Hot
    headline = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return f"{self.label} for {self.funnel.name}"

class ResultInsight(models.Model):
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='insights')
    tier = models.ForeignKey(ResultTier, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.TextField()

    def __str__(self):
        return self.title
