from rest_framework import serializers
from .models import Funnel, LandingPageContent, Question, Choice, Lead, Answer, ResultTier, ResultInsight

class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'value']

class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = ['id', 'text', 'type', 'order', 'weight', 'choices']

class LandingPageContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandingPageContent
        exclude = ['funnel']

class FunnelSerializer(serializers.ModelSerializer):
    landing_page = LandingPageContentSerializer(read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Funnel
        fields = ['id', 'name', 'slug', 'landing_page', 'questions']

class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ['id', 'funnel', 'first_name', 'email', 'phone', 'location']
        read_only_fields = ['id']

class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['question', 'choice', 'text_value']

class ResultInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultInsight
        fields = ['title', 'content']

class ResultTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultTier
        fields = ['label', 'headline', 'description']
