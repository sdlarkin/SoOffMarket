import os
import django
import sys

# Set up django environment
sys.path.append(os.path.join(os.getcwd(), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_api.settings')
django.setup()

from funnels.models import Funnel, LandingPageContent, Question, Choice, ResultTier, ResultInsight

def seed():
    # 1. Create Funnel
    funnel, created = Funnel.objects.get_or_create(
        slug='sleep-better',
        defaults={'name': 'Sleep Efficiency Assessment'}
    )
    if not created:
        print("Funnel already exists. Skipping seed.")
        return

    # 2. Landing Page Content
    LandingPageContent.objects.create(
        funnel=funnel,
        hero_hook_frustration="Feeling frustrated that you're exhausted every morning even though you're in bed for 8 hours?",
        hero_hook_results="Are you ready to wake up feeling refreshed and energized?",
        hero_subheading="Answer 15 questions to find out why your sleep quality is low and get a personalized 90-day improvement plan.",
        cta_text="Start the assessment",
        cta_microcopy="Takes 3 minutes. Completely free. Get immediate recommendations.",
        value_prop_area_1="Your Sleep Environment",
        value_prop_area_2="Your Evening Routine",
        value_prop_area_3="Your Sleep Nutrition",
        bio_name="Dr. Sarah Reston",
        bio_role="Sleep Scientist & Performance Coach",
        bio_text="Dr. Sarah has spent 15 years studying the neurobiology of sleep. She created this assessment to help high-performers master their recovery.",
        research_text="Based on a decade of clinical data, we've identified the 'Big 10' habits that dictate 90% of sleep quality.",
        stats_json=[
            "85% of adults struggle with sleep quality at least 3 nights a week.",
            "Optimizing sleep can improve cognitive performance by up to 40%.",
            "Consistent routines reduce cortisol spikes by 25%."
        ]
    )

    # 3. Best Practice Questions (1-10)
    questions_data = [
        ("Do you go to bed at the same time each night?", [("Yes", 10), ("No", 0)]),
        ("Do you avoid screens for at least 60 minutes before bed?", [("Yes", 10), ("No", 0)]),
        ("Is your bedroom completely dark during sleep?", [("Yes", 10), ("No", 0)]),
        ("Do you avoid caffeine after 2:00 PM?", [("Yes", 10), ("Sometimes", 5), ("No", 0)]),
        ("Do you have a consistent morning routine?", [("Yes", 10), ("No", 0)]),
        ("Do you exercise at least 3 times a week?", [("Yes", 10), ("No", 0)]),
        ("Is your bedroom temperature below 68°F (20°C)?", [("Yes", 10), ("No", 0)]),
        ("Do you avoid heavy meals within 3 hours of sleep?", [("Yes", 10), ("No", 0)]),
        ("Do you spend at least 15 mins in natural sunlight daily?", [("Yes", 10), ("No", 0)]),
        ("Do you use a sleep tracking device?", [("Yes", 10), ("No", 0)]),
    ]

    for i, (text, choices) in enumerate(questions_data):
        q = Question.objects.create(funnel=funnel, text=text, type='BEST_PRACTICE', order=i+1)
        for c_text, c_val in choices:
            Choice.objects.create(question=q, text=c_text, value=c_val)

    # 4. Big Five Questions (11-15)
    big_five = [
        ("Which best describes your current situation?", ["Struggling with insomnia", "Poor quality but okay duration", "Generally okay but want to optimize"]),
        ("Which best describes the most important outcome you want in 90 days?", ["Faster sleep onset", "Less waking up at night", "More deep sleep/energy"]),
        ("What is the biggest obstacle stopping you?", ["Stress/Anxiety", "Poor environment", "Irregular schedule"]),
        ("Which solution do you think would suit you best?", ["Home training/course", "Personal coaching", "Sleep gadgets/tools"]),
    ]

    for i, (text, choices) in enumerate(big_five):
        q = Question.objects.create(funnel=funnel, text=text, type='BIG_FIVE', order=i+11)
        for c_text in choices:
            Choice.objects.create(question=q, text=c_text, value=0)

    # 15. Open text
    Question.objects.create(funnel=funnel, text="Is there anything else we should know?", type='BIG_FIVE', order=15)

    # 5. Tiers
    ResultTier.objects.create(funnel=funnel, min_score=0, max_score=40, label='Cold', headline="Exhausted Foundations", description="Your sleep score indicates significant room for improvement. Your basic recovery habits are currently working against you.")
    ResultTier.objects.create(funnel=funnel, min_score=41, max_score=75, label='Warm', headline="Progressing Sleeper", description="You have some great habits in place, but several key 'leaks' are preventing you from reaching peak recovery.")
    ResultTier.objects.create(funnel=funnel, min_score=76, max_score=100, label='Hot', headline="Elite Recliner", description="You're doing almost everything right! You're in the top 5% of sleepers, and just need small tweaks for total mastery.")

    # 6. Insights (Generic)
    ResultInsight.objects.create(funnel=funnel, title="Your Environment", content="Focus on total blackout and cooler temperatures to trigger deeper sleep cycles.")
    ResultInsight.objects.create(funnel=funnel, title="The Routine Gap", content="The final 60 minutes of your day are the most critical. Consistency here will double your energy.")

    print("Success: Seeded 'sleep-better' funnel.")

if __name__ == "__main__":
    seed()
