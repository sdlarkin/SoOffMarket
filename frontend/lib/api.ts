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

// --- PARCELS API ---

export interface ParcelRating {
    rating: string;
    sort_order: number;
    notes: string;
    updated_at: string;
}

export interface ParcelOverview {
    id: string;
    parcel_id: string;
    lat: number | null;
    lon: number | null;
    deal_tier: string;
    duplex_friendliness: string;
    geo_priority: string;
    address: string;
    calc_acres: number;
    computed_acres: number | null;
    appraised_value: number;
    land_est_value: number | null;
    arv_comp_median: number | null;
    rating: string;
    sort_order: number;
    owner_adjacent: boolean;
    owner_lives_adjacent: boolean;
}

export interface ParcelListItem {
    id: string;
    parcel_id: string;
    address: string;
    owner_name: string;
    calc_acres: number;
    computed_acres: number | null;
    compactness: number | null;
    appraised_value: number;
    land_value: number;
    deal_tier: string;
    geo_priority: string;
    duplex_friendliness: string;
    duplex_ratio: number | null;
    land_est_value: number | null;
    arv_comp_median: number | null;
    water_provider: string;
    sewer_provider: string;
    utilities_score: string;
    lat: number | null;
    lon: number | null;
    assessor_link: string;
    rating: ParcelRating | null;
}

export interface OwnerDetail {
    id: string;
    name: string;
    first_name: string;
    last_name: string;
    mailing_address: string;
    phone_1: string;
    phone_1_type: string;
    phone_2: string;
    phone_2_type: string;
    phone_3: string;
    phone_3_type: string;
    email_1: string;
    email_2: string;
    email_3: string;
    age: string;
    skip_traced: boolean;
}

export interface ParcelDetail extends ParcelListItem {
    owner_detail: OwnerDetail | null;
    owner_name_2: string;
    owner_mailing: string;
    county: string;
    state: string;
    building_value: number;
    assessed_value: number;
    zoning: string;
    land_use_code: string;
    district: string;
    geometry_rings: number[][][];
    last_sale_date: string;
    last_sale_price: number;
    land_comp_count: number;
    land_comp_radius: string;
    land_comp_min: number | null;
    land_comp_max: number | null;
    land_comp_median: number | null;
    land_comp_avg_ppa: number | null;
    land_est_value: number | null;
    land_comp_details: string;
    arv_comp_count: number;
    arv_comp_radius: string;
    arv_comp_min: number | null;
    arv_comp_max: number | null;
    arv_comp_median: number | null;
    arv_comp_details: string;
    nearby_sfr: number;
    nearby_duplex: number;
    nearby_triplex: number;
    nearby_quad: number;
    nearby_total: number;
    owner_adjacent: boolean;
    owner_lives_adjacent: boolean;
    adjacent_details: string;
    comps: Array<{
        comp_type: string;
        comp_parcel_id: string;
        comp_address: string;
        comp_acres: number | null;
        distance_ft: number | null;
        sale_price: number | null;
        sale_date: string;
    }>;
}

export interface ParcelPaginationData {
    count: number;
    next: string | null;
    previous: string | null;
    results: ParcelListItem[];
}

export async function fetchParcelOverview(filters?: Record<string, string>): Promise<ParcelOverview[]> {
    const params = filters ? '?' + new URLSearchParams(filters).toString() : '';
    const res = await fetch(`${API_BASE_URL}/parcels/overview/${params}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch parcel overview');
    return res.json();
}

export async function fetchParcels(page: number = 1, filters?: Record<string, string>): Promise<ParcelPaginationData> {
    const params = new URLSearchParams({ page: String(page), ...filters });
    const res = await fetch(`${API_BASE_URL}/parcels/?${params}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch parcels');
    return res.json();
}

export async function fetchParcelDetail(id: string): Promise<ParcelDetail> {
    const res = await fetch(`${API_BASE_URL}/parcels/${id}/`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch parcel');
    return res.json();
}

export async function rateParcel(id: string, data: { rating: string; notes?: string; sort_order?: number }): Promise<ParcelRating> {
    const res = await fetch(`${API_BASE_URL}/parcels/${id}/rate/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to rate parcel');
    return res.json();
}

// ── Deals API (public, slug-based) ──

export interface BuyerSummary {
    id: string;
    name: string;
    slug: string;
    company_name: string;
    buybox_count: number;
}

export interface BuyBoxSummary {
    id: string;
    slug: string;
    asset_type: string;
    target_states: string;
    price_range: string;
    buyer_name: string;
    buyer_slug: string;
    parcel_count: number;
}

export interface DealsIndexResponse {
    buyer: { name: string; slug: string; company_name: string };
    buyboxes: BuyBoxSummary[];
}

export interface DealsBuyBoxResponse {
    buyer: { name: string; slug: string };
    buybox: { slug: string; asset_type: string; target_states: string; price_range: string };
    parcels: ParcelOverview[];
}

export async function fetchDealsIndex(): Promise<BuyerSummary[]> {
    const res = await fetch(`${API_BASE_URL}/deals/`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch deals');
    return res.json();
}

export async function fetchDealsBuyer(buyerSlug: string): Promise<DealsIndexResponse> {
    const res = await fetch(`${API_BASE_URL}/deals/${buyerSlug}/`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch buyer deals');
    return res.json();
}

export async function fetchDealsBuyBox(buyerSlug: string, buyboxSlug: string, filters?: Record<string, string>): Promise<DealsBuyBoxResponse> {
    const params = filters ? '?' + new URLSearchParams(filters).toString() : '';
    const res = await fetch(`${API_BASE_URL}/deals/${buyerSlug}/${buyboxSlug}/${params}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch buybox deals');
    return res.json();
}

export async function fetchDealsParcelDetail(buyerSlug: string, buyboxSlug: string, parcelId: string): Promise<ParcelDetail> {
    const res = await fetch(`${API_BASE_URL}/deals/${buyerSlug}/${buyboxSlug}/${parcelId}/`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch parcel detail');
    return res.json();
}

export async function reorderParcels(order: string[]): Promise<{ updated: number }> {
    const res = await fetch(`${API_BASE_URL}/parcels/reorder/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order }),
    });
    if (!res.ok) throw new Error('Failed to reorder parcels');
    return res.json();
}
