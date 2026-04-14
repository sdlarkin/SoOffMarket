# Directive: Dynamic Funnel Builder

This directive establishes the Standard Operating Procedure (SOP) for building a 3-part dynamic funnel system (Landing Page, Assessment, Results) where all content and logic are data-driven.

## 1. System Architecture
The system follows a decoupled Django/Next.js architecture:
- **Backend**: A dedicated Django app (`funnels`) providing a REST API via Django Rest Framework (DRF).
- **Frontend**: A Next.js application using Tailwind CSS, Framer Motion, and Lucide React to render dynamic components based on API data.

## 2. Technical Specifications

### 2.1 Backend Models
- `Funnel`: Root object identifying the funnel via a `slug`.
- `LandingPageContent`: Stores all copy variants for the landing page (Hooks, Value Props, Bio, Stats).
- `Question`: Multi-type questions (BEST_PRACTICE for scoring, BIG_FIVE for qualification).
- `Choice`: Predefined options for questions with point values for scoring.
- `Lead`: Captures contact info and stores the calculated `score` and `tier`.
- `Answer`: Links a `Lead` to their specific responses.
- `ResultTier`: Defines score ranges (0-100) and associated messaging (Cold/Warm/Hot).
- `ResultInsight`: Personalized text blocks shown based on the lead's tier.

### 2.2 Frontend Components
- `Hero`: Renders dynamic hooks and subheading.
- `ValueProp`: Displays focus areas in a grid.
- `Credibility`: Renders bio and research data.
- `AssessmentForm`: Manages multi-step state, transitions, and API submissions. Supports choice-based and open-text (`textarea`) inputs.
- `ResultsView`: Visualizes scores using a SVG gauge and displays personalized insights.

## 3. Implementation Workflow

### Phase 1: Backend Setup
Use `execution/setup_funnels_backend.py` to:
1. Create the `funnels` app.
2. Define models in `models.py`.
3. Register models in `admin.py`.
4. Implement DRF serializers and views (`FunnelViewSet`, `LeadViewSet`).
5. Configure URL routing.

### Phase 2: Frontend Setup
Use `execution/setup_funnels_frontend.py` to:
1. Create the API client utility (`lib/api.ts`).
2. Scaffolding UI components in `components/`.
3. Set up the dynamic route at `app/funnel/[slug]/page.tsx`.

## 5. System Recreation (Full Build From Scratch)
If you need to rebuild the entire system in a new environment, follow these steps using the provided execution scripts:

1. **Backend Build**: Run `python execution/setup_funnels_backend.py`.
   - This script creates the `funnels` app, writes all models, admin configs, serializers, views, and URL patterns, and registers them in the project settings.
   - Run `python manage.py makemigrations funnels` and `python manage.py migrate` after execution.

2. **Frontend Build**: Run `python execution/setup_funnels_frontend.py`.
   - This script generates the API client, all five core UI components, and the dynamic route handler.

3. **Funnel Creation**: 
   - Use `execution/create_funnel_view.py` to scaffold a new funnel entry.
   - Create a domain-specific seed script (e.g., `execution/seed_funnel.py`) to bulk-load detailed content.
