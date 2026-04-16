import Link from 'next/link';
import { fetchParcelDetail } from '@/lib/api';
import ParcelDetailMapWrapper from '@/components/ParcelDetailMapWrapper';
import ParcelRatingControls from '@/components/ParcelRatingControls';
import { ExternalLink, MapPin, Droplets, Home, TrendingUp, ArrowLeft } from 'lucide-react';

function fmt(val: number | null | undefined): string {
    if (!val && val !== 0) return '-';
    return '$' + val.toLocaleString();
}

function Badge({ children, color }: { children: React.ReactNode; color: string }) {
    return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>{children}</span>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">{title}</h3>
            {children}
        </div>
    );
}

function DataRow({ label, value, accent }: { label: string; value: string | React.ReactNode; accent?: boolean }) {
    return (
        <div className="flex justify-between items-center py-1.5 border-b border-slate-50 last:border-0">
            <span className="text-sm text-slate-500">{label}</span>
            <span className={`text-sm font-semibold ${accent ? 'text-emerald-600' : 'text-slate-900'}`}>{value}</span>
        </div>
    );
}

export default async function ParcelDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    const p = await fetchParcelDetail(id);

    const gradeColors: Record<string, string> = {
        A: 'bg-emerald-100 text-emerald-700',
        B: 'bg-blue-100 text-blue-700',
        C: 'bg-amber-100 text-amber-700',
        D: 'bg-slate-100 text-slate-600',
    };

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-white border-b border-slate-200 px-6 py-4">
                <div className="max-w-7xl mx-auto">
                    <Link href="/parcels" className="text-sm text-blue-600 hover:underline flex items-center gap-1 mb-2">
                        <ArrowLeft size={14} /> Back to all parcels
                    </Link>
                    <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-bold text-slate-900">{p.address || 'No address'}</h1>
                        <Badge color={gradeColors[p.duplex_friendliness] || 'bg-slate-100 text-slate-600'}>
                            Grade {p.duplex_friendliness}
                        </Badge>
                        <Badge color="bg-slate-100 text-slate-600">{p.parcel_id}</Badge>
                    </div>
                    <p className="text-sm text-slate-500 mt-1">
                        {p.owner_name}{p.owner_name_2 ? ` & ${p.owner_name_2}` : ''} — {p.owner_mailing}
                    </p>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-6 py-6">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left column: Map + Rating + Links */}
                    <div className="lg:col-span-1 space-y-4">
                        {/* Map */}
                        <div className="rounded-xl overflow-hidden border border-slate-200">
                            {p.lat && p.lon ? (
                                <ParcelDetailMapWrapper
                                    lat={p.lat}
                                    lon={p.lon}
                                    rings={p.geometry_rings || []}
                                    height="350px"
                                />
                            ) : (
                                <div className="h-[350px] bg-slate-100 flex items-center justify-center text-slate-400">
                                    No coordinates available
                                </div>
                            )}
                        </div>

                        {/* External Links */}
                        <div className="flex gap-2">
                            {p.lat && p.lon && (
                                <>
                                    <a
                                        href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${p.lat},${p.lon}&heading=0&pitch=0&fov=90`}
                                        target="_blank"
                                        className="flex-1 flex items-center justify-center gap-1.5 bg-white border border-slate-200 rounded-lg py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition"
                                    >
                                        <MapPin size={14} /> Street View
                                    </a>
                                    <a
                                        href={`https://www.google.com/maps/@${p.lat},${p.lon},18z/data=!3m1!1e1`}
                                        target="_blank"
                                        className="flex-1 flex items-center justify-center gap-1.5 bg-white border border-slate-200 rounded-lg py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition"
                                    >
                                        <ExternalLink size={14} /> Google Maps
                                    </a>
                                </>
                            )}
                            {p.assessor_link && (
                                <a
                                    href={p.assessor_link}
                                    target="_blank"
                                    className="flex-1 flex items-center justify-center gap-1.5 bg-white border border-slate-200 rounded-lg py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition"
                                >
                                    <ExternalLink size={14} /> Assessor
                                </a>
                            )}
                        </div>

                        {/* Rating */}
                        <div className="bg-white rounded-xl border border-slate-200 p-4">
                            <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Rating</h3>
                            <ParcelRatingControls
                                parcelId={p.id}
                                currentRating={p.rating?.rating}
                                currentNotes={p.rating?.notes}
                            />
                        </div>
                    </div>

                    {/* Right column: Data sections */}
                    <div className="lg:col-span-2 space-y-4">
                        {/* Values */}
                        <Section title="Values">
                            <div className="grid grid-cols-2 gap-x-8">
                                <DataRow label="Appraised Value" value={fmt(p.appraised_value)} />
                                <DataRow label="Assessed Value" value={fmt(p.assessed_value)} />
                                <DataRow label="Land Value" value={fmt(p.land_value)} />
                                <DataRow label="Building Value" value={fmt(p.building_value)} />
                                <DataRow label="Last Sale Price" value={fmt(p.last_sale_price)} />
                                <DataRow label="Last Sale Date" value={p.last_sale_date || '-'} />
                            </div>
                        </Section>

                        {/* Land Details */}
                        <Section title="Land Details">
                            <div className="grid grid-cols-2 gap-x-8">
                                <DataRow label="Computed Acres" value={p.computed_acres?.toFixed(3) || '-'} />
                                <DataRow label="GIS Acres" value={p.calc_acres?.toString() || '-'} />
                                <DataRow label="Compactness" value={p.compactness?.toFixed(3) || '-'} />
                                <DataRow label="Zoning" value={p.zoning || '-'} />
                                <DataRow label="Land Use Code" value={p.land_use_code || '-'} />
                                <DataRow label="District" value={p.district || '-'} />
                            </div>
                        </Section>

                        {/* Utilities */}
                        <Section title="Utilities">
                            <div className="grid grid-cols-2 gap-x-8">
                                <DataRow label="Water" value={
                                    p.water_provider
                                        ? <span className="flex items-center gap-1"><Droplets size={14} className="text-blue-500" />{p.water_provider}</span>
                                        : <span className="text-red-500">None</span>
                                } />
                                <DataRow label="Sewer" value={p.sewer_provider || <span className="text-red-500">None</span>} />
                                <DataRow label="Score" value={p.utilities_score || '-'} />
                                <DataRow label="Deal Tier" value={p.deal_tier || '-'} />
                            </div>
                        </Section>

                        {/* Duplex Friendliness */}
                        <Section title="Duplex Friendliness">
                            <div className="flex items-center gap-3 mb-3">
                                <Badge color={gradeColors[p.duplex_friendliness] || 'bg-slate-100'}>
                                    Grade {p.duplex_friendliness}
                                </Badge>
                                <span className="text-sm text-slate-600">
                                    {p.duplex_ratio?.toFixed(1)}% multi-family within 0.25mi
                                </span>
                            </div>
                            <div className="grid grid-cols-4 gap-4 text-center text-sm">
                                <div>
                                    <div className="text-2xl font-bold text-slate-700">{p.nearby_sfr}</div>
                                    <div className="text-slate-400">SFR</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-bold text-emerald-600">{p.nearby_duplex}</div>
                                    <div className="text-slate-400">Duplex</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-bold text-blue-600">{p.nearby_triplex}</div>
                                    <div className="text-slate-400">Triplex</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-bold text-purple-600">{p.nearby_quad}</div>
                                    <div className="text-slate-400">Quad</div>
                                </div>
                            </div>
                        </Section>

                        {/* Land Comps */}
                        <Section title="Land Comps">
                            <div className="grid grid-cols-2 gap-x-8 mb-3">
                                <DataRow label="Comps Found" value={`${p.land_comp_count} (${p.land_comp_radius})`} />
                                <DataRow label="Estimated Land Value" value={fmt(p.land_est_value)} accent />
                                <DataRow label="Comp Range" value={`${fmt(p.land_comp_min)} - ${fmt(p.land_comp_max)}`} />
                                <DataRow label="Median" value={fmt(p.land_comp_median)} />
                                <DataRow label="Avg $/Acre" value={fmt(p.land_comp_avg_ppa)} />
                            </div>
                            {p.land_comp_details && (
                                <div className="text-xs text-slate-500 bg-slate-50 rounded-lg p-3 mt-2">
                                    {p.land_comp_details}
                                </div>
                            )}
                        </Section>

                        {/* ARV Comps */}
                        <Section title="ARV Comps (After Reno Value)">
                            <div className="grid grid-cols-2 gap-x-8 mb-3">
                                <DataRow label="Comps Found" value={`${p.arv_comp_count} (${p.arv_comp_radius})`} />
                                <DataRow label="ARV Median" value={fmt(p.arv_comp_median)} accent />
                                <DataRow label="Comp Range" value={`${fmt(p.arv_comp_min)} - ${fmt(p.arv_comp_max)}`} />
                            </div>
                            {p.arv_comp_details && (
                                <div className="text-xs text-slate-500 bg-slate-50 rounded-lg p-3 mt-2">
                                    {p.arv_comp_details}
                                </div>
                            )}
                        </Section>
                    </div>
                </div>
            </div>
        </div>
    );
}
