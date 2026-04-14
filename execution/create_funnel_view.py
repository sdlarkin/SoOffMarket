import os
import django
import sys

# Set up django environment
sys.path.append(os.path.join(os.getcwd(), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_api.settings')
django.setup()

from funnels.models import Funnel, LandingPageContent, Question, Choice, ResultTier

def create_generic_funnel(slug, name):
    funnel, created = Funnel.objects.get_or_create(
        slug=slug,
        defaults={'name': name}
    )
    if not created:
        print(f"Funnel {slug} already exists.")
        return funnel

    # Create dummy landing content
    LandingPageContent.objects.create(
        funnel=funnel,
        hero_hook_frustration=f"Tired of {name} problems?",
        hero_hook_results=f"Ready for {name} success?",
        hero_subheading="Take the assessment to find out.",
        value_prop_area_1="Area 1",
        value_prop_area_2="Area 2",
        value_prop_area_3="Area 3"
    )

    # Create one sample question
    q = Question.objects.create(funnel=funnel, text="Sample Question?", type='BEST_PRACTICE', order=1)
    Choice.objects.create(question=q, text="Yes", value=100)
    Choice.objects.create(question=q, text="No", value=0)

    # Create tiers
    ResultTier.objects.create(funnel=funnel, min_score=0, max_score=100, label='Default', headline="Your Results", description="Overview text.")

    print(f"Success: Created generic funnel: {slug}")
    return funnel

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Manage Funnels")
    parser.add_argument("action", choices=["create"])
    parser.add_argument("--slug", required=True)
    parser.add_argument("--name", required=True)
    
    args = parser.parse_args()
    if args.action == "create":
        create_generic_funnel(args.slug, args.name)
