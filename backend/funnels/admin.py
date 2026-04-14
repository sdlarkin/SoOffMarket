from django.contrib import admin
from .models import Funnel, LandingPageContent, Question, Choice, Lead, Answer, ResultTier, ResultInsight

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 3

class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'funnel', 'type', 'order')
    list_filter = ('funnel', 'type')
    inlines = [ChoiceInline]

class LandingPageContentInline(admin.StackedInline):
    model = LandingPageContent

class ResultTierInline(admin.TabularInline):
    model = ResultTier

class FunnelAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [LandingPageContentInline, ResultTierInline]

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question', 'choice', 'text_value')

class LeadAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'email', 'score', 'tier_label', 'created_at')
    readonly_fields = ('id', 'created_at')
    inlines = [AnswerInline]

admin.site.register(Funnel, FunnelAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Lead, LeadAdmin)
admin.site.register(ResultInsight)
