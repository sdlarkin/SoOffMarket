import os
import django
import sys

# Set up django environment
sys.path.append(os.path.join(os.getcwd(), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_api.settings')
django.setup()

from funnels.models import Funnel, LandingPageContent, Question, Choice, ResultTier, ResultInsight

def seed_cyber():
    # 1. Get or Create Funnel
    funnel, _ = Funnel.objects.get_or_create(
        slug='cybersecurity-audit',
        defaults={'name': 'Cybersecurity Readiness Audit'}
    )

    # 2. Add Landing Content
    LandingPageContent.objects.update_or_create(
        funnel=funnel,
        defaults={
            'hero_hook_frustration': "Are you worried that a single data breach could bankrupt your business?",
            'hero_hook_results': "Are you ready to build a bulletproof cybersecurity defense?",
            'hero_subheading': "Answer 15 questions to identify your security vulnerabilities and get a priority-ranked remediation list.",
            'cta_text': "Start the Audit",
            'value_prop_area_1': "Network Security",
            'value_prop_area_2': "Employee Protocols",
            'value_prop_area_3': "Cloud Protection",
            'bio_name': "Alex Firewall",
            'bio_role': "CISSP & Cybersecurity Consultant",
            'bio_text': "Alex has mitigated over 500 ransomware attacks for Fortune 500 companies.",
            'research_text': "60% of small businesses collapse within 6 months of a major cyber attack.",
            'stats_json': [
                "Total global cybercrime costs will reach $10.5 trillion by 2025.",
                "95% of breaches are caused by human error.",
                "Multi-factor authentication prevents 99% of bulk phishing attacks."
            ]
        }
    )

    # 3. Questions
    # Clear existing questions for this test to avoid duplicates
    funnel.questions.all().delete()
    
    q_data = [
        ("Do you use Multi-Factor Authentication (MFA) on all email accounts?", [("Yes", 10), ("No", 0)]),
        ("Do you provide monthly security training to all staff?", [("Yes", 10), ("No", 0)]),
        ("Are your local backups isolated from your main network?", [("Yes", 10), ("No", 0)]),
        ("Do you have a documented Incident Response Plan?", [("Yes", 10), ("No", 0)]),
    ]

    for i, (text, choices) in enumerate(q_data):
        q = Question.objects.create(funnel=funnel, text=text, type='BEST_PRACTICE', order=i+1)
        for ct, cv in choices:
            Choice.objects.create(question=q, text=ct, value=cv)

    # Big Five
    q5 = Question.objects.create(funnel=funnel, text="Which solution suits you best?", type='BIG_FIVE', order=14)
    Choice.objects.create(question=q5, text="One-to-one Consulting", value=0)
    Choice.objects.create(question=q5, text="Self-study Course", value=0)

    # 4. Tiers and Insights
    funnel.tiers.all().delete()
    ResultTier.objects.create(funnel=funnel, min_score=0, max_score=50, label='Cold', headline="Critical Risk Level", description="Your infrastructure is highly vulnerable. Immediate action is required to prevent data loss.")
    ResultTier.objects.create(funnel=funnel, min_score=51, max_score=100, label='Hot', headline="Strong Defense", description="You have a solid foundation. Focus on advanced threat hunting to reach total resilience.")

    print("Success: Populated 'cybersecurity-audit' funnel content.")

if __name__ == "__main__":
    seed_cyber()
