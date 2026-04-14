from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import models
from .models import Funnel, Lead, Answer, ResultTier, Question, Choice
from .serializers import FunnelSerializer, LeadSerializer, AnswerSerializer, ResultTierSerializer, ResultInsightSerializer

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
        
        # Save answers
        total_score = 0
        possible_score = 0
        
        for ans in answers_data:
            question_id = ans.get('question')
            choice_id = ans.get('choice')
            text_value = ans.get('text_value', '')
            
            question = get_object_or_404(Question, id=question_id)
            choice = None
            if choice_id:
                choice = get_object_or_404(Choice, id=choice_id)
                if question.type == 'BEST_PRACTICE':
                    total_score += choice.value * question.weight
                    # We assume 100 is max for simplicity or we can calculate based on max choice value
            
            Answer.objects.create(
                lead=lead,
                question=question,
                choice=choice,
                text_value=text_value
            )
            
            if question.type == 'BEST_PRACTICE':
                # Simplified max score: find max choice value for this question
                max_choice = question.choices.order_by('-value').first()
                if max_choice:
                    possible_score += max_choice.value * question.weight

        # Calculate normalized score (0-100)
        final_score = 0
        if possible_score > 0:
            final_score = (total_score / possible_score) * 100
        
        lead.score = final_score
        
        # Determine tier
        tier = ResultTier.objects.filter(
            funnel=lead.funnel, 
            min_score__lte=final_score, 
            max_score__gte=final_score
        ).first()
        
        if tier:
            lead.tier_label = tier.label
            # Logic for next_step_type can be more complex, for now simple mapping
            # In a real scenario, you'd check qualification questions too
            if tier.label == 'Hot':
                lead.next_step_type = 'High Qualified'
            elif tier.label == 'Warm':
                lead.next_step_type = 'Moderately Qualified'
            else:
                lead.next_step_type = 'Early Stage'
        
        lead.save()
        
        # Return results
        tier_data = ResultTierSerializer(tier).data if tier else None
        insights = lead.funnel.insights.filter(models.Q(tier=tier) | models.Q(tier__isnull=True))
        insights_data = ResultInsightSerializer(insights, many=True).data

        return Response({
            'score': final_score,
            'tier': tier_data,
            'insights': insights_data,
            'next_step_type': lead.next_step_type
        })
