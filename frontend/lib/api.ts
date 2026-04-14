const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export interface LandingPageContent {
    hero_hook_frustration: string;
    hero_hook_results: string;
    hero_subheading: string;
    cta_text: string;
    cta_microcopy: string;
    value_prop_area_1: string;
    value_prop_area_2: string;
    value_prop_area_3: string;
    bio_name: string;
    bio_role: string;
    bio_text: string;
    research_text: string;
    stats_json: string[];
}

export interface Choice {
    id: number;
    text: string;
    value: number;
}

export interface Question {
    id: number;
    text: string;
    type: 'BEST_PRACTICE' | 'BIG_FIVE';
    order: number;
    choices: Choice[];
}

export interface FunnelData {
    id: number;
    name: string;
    slug: string;
    landing_page: LandingPageContent;
    questions: Question[];
}

export interface ResultData {
    score: number;
    tier: {
        label: string;
        headline: string;
        description: string;
    };
    insights: {
        title: string;
        content: string;
    }[];
    next_step_type: string;
}

export async function fetchFunnel(slug: string): Promise<FunnelData> {
    const res = await fetch(`${API_BASE_URL}/funnels/${slug}/`);
    if (!res.ok) throw new Error('Failed to fetch funnel');
    return res.json();
}

export async function createLead(funnelId: number, data: { first_name: string; email: string; phone?: string }): Promise<{ id: string }> {
    const res = await fetch(`${API_BASE_URL}/leads/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ funnel: funnelId, ...data }),
    });
    if (!res.ok) throw new Error('Failed to create lead');
    return res.json();
}

export async function submitAssessment(leadId: string, answers: { question: number; choice?: number; text_value?: string }[]): Promise<ResultData> {
    const res = await fetch(`${API_BASE_URL}/leads/${leadId}/submit-assessment/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
    });
    if (!res.ok) throw new Error('Failed to submit assessment');
    return res.json();
}

export interface PropertyMatchList {
    id: string;
    property_name: string;
    property_state: string;
    buyer_name: string;
    asset_type: string;
    match_score: number;
    match_reason: string;
    created_at: string;
}

export interface MatchPaginationData {
    count: number;
    next: string | null;
    previous: string | null;
    results: PropertyMatchList[];
}

export async function fetchMatches(page: number = 1): Promise<MatchPaginationData> {
    const res = await fetch(`${API_BASE_URL}/engine/matches/?page=${page}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch matches');
    return res.json();
}

export async function fetchMatchDetails(id: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/engine/matches/${id}/`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch match details');
    return res.json();
}

// --- NEW PROPERTY-CENTRIC API REQUESTS ---

export interface MatchedPropertyList {
    id: string;
    company_name: string;
    address: string;
    city: string;
    state: string;
    zip_code: string;
    industry: string;
    match_count: number;
}

export interface MatchedPropertyPagination {
    count: number;
    next: string | null;
    previous: string | null;
    results: MatchedPropertyList[];
}

export async function fetchMatchedProperties(page: number = 1): Promise<MatchedPropertyPagination> {
    const res = await fetch(`${API_BASE_URL}/engine/matched-properties/?page=${page}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch matched properties');
    return res.json();
}

export async function fetchMatchedPropertyDetails(id: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/engine/matched-properties/${id}/`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch detailed property matches');
    return res.json();
}
