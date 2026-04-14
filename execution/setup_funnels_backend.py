import os
import subprocess

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    print(f"Created/Updated: {path}")

def setup_backend():
    backend_dir = os.path.join(os.getcwd(), 'backend')
    app_name = 'funnels'
    app_dir = os.path.join(backend_dir, app_name)

    # 1. Startapp if it doesn't exist
    if not os.path.exists(app_dir):
        print(f"Creating app: {app_name}")
        subprocess.run(["python", "manage.py", "startapp", app_name], cwd=backend_dir, check=True)

    # 2. Add Models
    models_content = """from django.db import models
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
    hero_hook_frustration = models.TextField()
    hero_hook_results = models.TextField()
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
    stats_json = models.JSONField(default=list, blank=True)

class Question(models.Model):
    TYPES = (('BEST_PRACTICE', 'Best Practice'), ('BIG_FIVE', 'Big Five'))
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    type = models.CharField(max_length=20, choices=TYPES)
    order = models.PositiveIntegerField(default=0)
    weight = models.FloatField(default=1.0)
    class Meta: ordering = ['order']

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    value = models.FloatField(default=0)

class Lead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=255, blank=True)
    score = models.FloatField(null=True, blank=True)
    tier_label = models.CharField(max_length=50, blank=True)
    next_step_type = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Answer(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)
    text_value = models.TextField(blank=True)

class ResultTier(models.Model):
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='tiers')
    min_score = models.FloatField(); max_score = models.FloatField()
    label = models.CharField(max_length=50); headline = models.CharField(max_length=255); description = models.TextField()

class ResultInsight(models.Model):
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='insights')
    tier = models.ForeignKey(ResultTier, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255); content = models.TextField()
"""
    write_file(os.path.join(app_dir, 'models.py'), models_content)

    # 3. Add Admin
    admin_content = """from django.contrib import admin
from .models import Funnel, LandingPageContent, Question, Choice, Lead, Answer, ResultTier, ResultInsight
class ChoiceInline(admin.TabularInline): model = Choice; extra = 3
class QuestionAdmin(admin.ModelAdmin): list_display = ('text', 'funnel', 'type', 'order'); inlines = [ChoiceInline]
class LandingPageContentInline(admin.StackedInline): model = LandingPageContent
class FunnelAdmin(admin.ModelAdmin): list_display = ('name', 'slug'); prepopulated_fields = {'slug': ('name',)}; inlines = [LandingPageContentInline]
admin.site.register(Funnel, FunnelAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Lead, admin.ModelAdmin)
admin.site.register(ResultInsight)
"""
    write_file(os.path.join(app_dir, 'admin.py'), admin_content)

    # 4. Add Serializers
    serializers_content = """from rest_framework import serializers
from .models import Funnel, LandingPageContent, Question, Choice, Lead, Answer, ResultTier, ResultInsight
class ChoiceSerializer(serializers.ModelSerializer):
    class Meta: model = Choice; fields = ['id', 'text', 'value']
class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)
    class Meta: model = Question; fields = ['id', 'text', 'type', 'order', 'choices']
class LandingPageContentSerializer(serializers.ModelSerializer):
    class Meta: model = LandingPageContent; exclude = ['funnel']
class FunnelSerializer(serializers.ModelSerializer):
    landing_page = LandingPageContentSerializer(read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    class Meta: model = Funnel; fields = ['id', 'name', 'slug', 'landing_page', 'questions']
class LeadSerializer(serializers.ModelSerializer):
    class Meta: model = Lead; fields = ['id', 'funnel', 'first_name', 'email', 'phone', 'location']; read_only_fields = ['id']
class ResultTierSerializer(serializers.ModelSerializer):
    class Meta: model = ResultTier; fields = ['label', 'headline', 'description']
class ResultInsightSerializer(serializers.ModelSerializer):
    class Meta: model = ResultInsight; fields = ['title', 'content']
"""
    write_file(os.path.join(app_dir, 'serializers.py'), serializers_content)

    # 5. Add Views
    views_content = """from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Funnel, Lead, Answer, ResultTier, Question, Choice, ResultInsight
from .serializers import FunnelSerializer, LeadSerializer, ResultTierSerializer, ResultInsightSerializer

class FunnelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Funnel.objects.filter(is_active=True)
    serializer_class = FunnelSerializer
    lookup_field = 'slug'

class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    @action(detail=True, methods=['post'], url_path='submit-assessment')
    def submit_assessment(self, request, pk=None):
        lead = get_object_or_404(Lead, id=pk)
        answers_data = request.data.get('answers', [])
        total_score = 0; possible_score = 0
        for ans in answers_data:
            q = get_object_or_404(Question, id=ans.get('question'))
            choice = None
            if ans.get('choice'):
                choice = get_object_or_404(Choice, id=ans.get('choice'))
                if q.type == 'BEST_PRACTICE': total_score += choice.value * q.weight
            Answer.objects.create(lead=lead, question=q, choice=choice, text_value=ans.get('text_value', ''))
            if q.type == 'BEST_PRACTICE':
                max_choice = q.choices.order_by('-value').first()
                if max_choice: possible_score += max_choice.value * q.weight
        final_score = (total_score / possible_score * 100) if possible_score > 0 else 0
        lead.score = final_score
        tier = ResultTier.objects.filter(funnel=lead.funnel, min_score__lte=final_score, max_score__gte=final_score).first()
        if tier:
            lead.tier_label = tier.label
            lead.next_step_type = 'High Qualified' if tier.label == 'Hot' else 'Moderately Qualified' if tier.label == 'Warm' else 'Early Stage'
        lead.save()
        insights = lead.funnel.insights.all() # Simplified
        return Response({'score': final_score, 'tier': ResultTierSerializer(tier).data if tier else None, 'insights': ResultInsightSerializer(insights, many=True).data, 'next_step_type': lead.next_step_type})
"""
    write_file(os.path.join(app_dir, 'views.py'), views_content)

    # 6. Add URLs
    urls_content = """from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FunnelViewSet, LeadViewSet
router = DefaultRouter(); router.register(r'funnels', FunnelViewSet); router.register(r'leads', LeadViewSet)
urlpatterns = [path('', include(router.urls))]
"""
    write_file(os.path.join(app_dir, 'urls.py'), urls_content)

    # 7. Update Project
    settings_path = os.path.join(backend_dir, 'backend_api', 'settings.py')
    with open(settings_path, 'r') as f: content = f.read()
    if "'funnels'" not in content:
        content = content.replace("INSTALLED_APPS = [", "INSTALLED_APPS = [\n    'funnels',\n    'rest_framework',")
        write_file(settings_path, content)

    project_urls_path = os.path.join(backend_dir, 'backend_api', 'urls.py')
    with open(project_urls_path, 'r') as f: urls_content = f.read()
    if 'funnels.urls' not in urls_content:
        urls_content = urls_content.replace('from django.urls import path', 'from django.urls import path, include')
        urls_content = urls_content.replace('urlpatterns = [', 'urlpatterns = [\n    path("api/", include("funnels.urls")),')
        write_file(project_urls_path, urls_content)

def create_admin_account():
    import django
    from django.contrib.auth.models import User
    try:
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'password123')
            print("Superuser 'admin' created with password 'password123'")
    except Exception as e:
        print(f"Could not create superuser (migrations might not be applied): {e}")

if __name__ == "__main__":
    setup_backend()
    
    # Set up django environment to create superuser
    backend_dir = os.path.join(os.getcwd(), 'backend')
    import sys
    sys.path.append(backend_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_api.settings')
    try:
        import django
        django.setup()
        create_admin_account()
    except Exception as e:
        print(f"Skipping superuser creation: {e}")
