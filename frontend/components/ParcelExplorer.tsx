'use client';

import { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { fetchParcelOverview, fetchParcelDetail, rateParcel, reorderParcels } from '@/lib/api';
import type { ParcelOverview, ParcelDetail } from '@/lib/api';
import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown, X, ExternalLink, MapPin, Search, GripVertical, List } from 'lucide-react';
import {
    DndContext, closestCenter, PointerSensor, TouchSensor, useSensor, useSensors,
    type DragEndEvent,
} from '@dnd-kit/core';
import {
    SortableContext, verticalListSortingStrategy, useSortable, arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const ParcelMapFull = dynamic(() => import('@/components/ParcelMapFull'), { ssr: false });

function fmt(val: number | null | undefined): string {
    if (!val && val !== 0) return '-';
    return '$' + val.toLocaleString();
}

function gradeColor(grade: string) {
    if (grade === 'A') return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
    if (grade === 'B') return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
    return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

function ratingDot(rating: string) {
    if (rating === 'yes') return 'bg-emerald-400';
    if (rating === 'maybe') return 'bg-amber-400';
    if (rating === 'no') return 'bg-red-400';
    if (rating === 'skip') return 'bg-slate-400';
    return 'bg-transparent border border-slate-600';
}

const RATING_BUTTONS = [
    { value: 'yes', label: 'Yes', cls: 'bg-emerald-500 hover:bg-emerald-400 active:bg-emerald-400', activeCls: 'bg-emerald-400 ring-2 ring-emerald-300' },
    { value: 'maybe', label: 'Maybe', cls: 'bg-amber-500 hover:bg-amber-400 active:bg-amber-400', activeCls: 'bg-amber-400 ring-2 ring-amber-300' },
    { value: 'no', label: 'No', cls: 'bg-red-500 hover:bg-red-400 active:bg-red-400', activeCls: 'bg-red-400 ring-2 ring-red-300' },
    { value: 'skip', label: 'Skip', cls: 'bg-slate-600 hover:bg-slate-500 active:bg-slate-500', activeCls: 'bg-slate-500 ring-2 ring-slate-400' },
];

// ── Parcel card (used in both sortable and static modes) ──
function ParcelCardContent({ p, isSelected, rank }: { p: ParcelOverview; isSelected: boolean; rank: number | null }) {
    return (
        <>
            <div className="flex items-center gap-2 mb-1">
                {rank !== null && <span className="text-[10px] font-bold text-slate-500 w-4 text-right flex-shrink-0">#{rank}</span>}
                <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${ratingDot(p.rating)}`} />
                <span className="text-sm font-medium text-white truncate">{p.address || 'No address'}</span>
                {p.owner_lives_adjacent && <span className="text-[9px] px-1 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30 flex-shrink-0">ADJ</span>}
                {p.owner_adjacent && !p.owner_lives_adjacent && <span className="text-[9px] px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 flex-shrink-0">ADJ</span>}
            </div>
            <div className="flex items-center gap-1.5 pl-5 text-xs flex-wrap">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${gradeColor(p.duplex_friendliness)}`}>{p.duplex_friendliness}</span>
                <span className="text-slate-500">{(p.computed_acres || p.calc_acres)?.toFixed(2)}ac</span>
                <span className="text-slate-600">|</span>
                <span className="text-slate-400">{fmt(p.appraised_value)}</span>
                <span className="text-slate-600">|</span>
                <span className="text-emerald-400">{fmt(p.land_est_value)}</span>
                <span className="text-slate-600">|</span>
                <span className="text-blue-400">{fmt(p.arv_comp_median)}</span>
            </div>
        </>
    );
}

function SortableParcelCard({ parcel: p, isSelected, rank, onSelect }: {
    parcel: ParcelOverview; isSelected: boolean; rank: number | null; onSelect: () => void;
}) {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: p.id });
    const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };

    return (
        <div ref={setNodeRef} style={style} onClick={onSelect}
            className={`flex items-center gap-1 px-2 py-2.5 border-b border-slate-800 cursor-pointer transition-colors ${
                isSelected ? 'bg-slate-700/60 border-l-2 border-l-rose-500' : 'hover:bg-slate-800/60 border-l-2 border-l-transparent'
            }`}>
            <div {...attributes} {...listeners} className="flex-shrink-0 cursor-grab active:cursor-grabbing text-slate-600 hover:text-slate-400 px-1 touch-none">
                <GripVertical size={14} />
            </div>
            <div className="flex-1 min-w-0">
                <ParcelCardContent p={p} isSelected={isSelected} rank={rank} />
            </div>
        </div>
    );
}

function StaticParcelCard({ parcel: p, isSelected, onSelect }: {
    parcel: ParcelOverview; isSelected: boolean; onSelect: () => void;
}) {
    return (
        <div onClick={onSelect}
            className={`px-3 py-2.5 border-b border-slate-800 cursor-pointer transition-colors ${
                isSelected ? 'bg-slate-700/60 border-l-2 border-l-rose-500' : 'hover:bg-slate-800/60 border-l-2 border-l-transparent'
            }`}>
            <ParcelCardContent p={p} isSelected={isSelected} rank={null} />
        </div>
    );
}

// ── Main Explorer ──
export default function ParcelExplorer() {
    const [parcels, setParcels] = useState<ParcelOverview[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [detail, setDetail] = useState<ParcelDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [mobileSheet, setMobileSheet] = useState<'none' | 'list' | 'detail'>('none');
    const [search, setSearch] = useState('');
    const [filterRating, setFilterRating] = useState('all');
    const [ratingState, setRatingState] = useState('');
    const [notesState, setNotesState] = useState('');
    const [saving, setSaving] = useState(false);

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
        useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } })
    );

    useEffect(() => {
        fetchParcelOverview().then(setParcels);
        // Default sidebar open on desktop
        if (window.innerWidth >= 1024) setSidebarOpen(true);
    }, []);

    const selectParcel = useCallback(async (id: string) => {
        // If already selected, just reopen the detail sheet
        if (id === selectedId && detail) {
            setMobileSheet('detail');
            return;
        }
        setSelectedId(id);
        setDetailLoading(true);
        setMobileSheet('detail');
        try {
            const d = await fetchParcelDetail(id);
            setDetail(d);
            setRatingState(d.rating?.rating || '');
            setNotesState(d.rating?.notes || '');
        } catch (e) { console.error(e); }
        setDetailLoading(false);
    }, [selectedId, detail]);

    async function handleRate(value: string) {
        if (!selectedId) return;
        setSaving(true);
        try {
            await rateParcel(selectedId, { rating: value, notes: notesState });
            setRatingState(value);
            setParcels(prev => prev.map(p => p.id === selectedId ? { ...p, rating: value } : p));
        } catch (e) { console.error(e); }
        setSaving(false);
    }

    async function handleNotesSave() {
        if (!selectedId || !ratingState) return;
        setSaving(true);
        try { await rateParcel(selectedId, { rating: ratingState, notes: notesState }); }
        catch (e) { console.error(e); }
        setSaving(false);
    }

    const isDraggable = filterRating === 'yes' || filterRating === 'maybe';
    const filtered = parcels
        .filter(p => {
            if (filterRating !== 'all') {
                const r = p.rating || '';
                if (filterRating === 'unrated' && r !== '') return false;
                if (filterRating !== 'unrated' && r !== filterRating) return false;
            }
            if (search) {
                const s = search.toLowerCase();
                return (p.address + ' ' + p.parcel_id).toLowerCase().includes(s);
            }
            return true;
        })
        .sort((a, b) => isDraggable ? (a.sort_order || 0) - (b.sort_order || 0) : 0);

    async function handleDragEnd(event: DragEndEvent) {
        const { active, over } = event;
        if (!over || active.id === over.id) return;
        const oldIndex = filtered.findIndex(p => p.id === active.id);
        const newIndex = filtered.findIndex(p => p.id === over.id);
        const reordered = arrayMove(filtered, oldIndex, newIndex);
        setParcels(prev => prev.map(p => {
            const idx = reordered.findIndex(r => r.id === p.id);
            return idx >= 0 ? { ...p, sort_order: idx } : p;
        }));
        try { await reorderParcels(reordered.map(p => p.id)); } catch (e) { console.error(e); }
    }

    const stats = {
        total: parcels.length,
        rated: parcels.filter(p => p.rating && p.rating !== '').length,
        yes: parcels.filter(p => p.rating === 'yes').length,
        maybe: parcels.filter(p => p.rating === 'maybe').length,
        no: parcels.filter(p => p.rating === 'no').length,
    };

    const d = detail;

    // ── Shared sidebar content ──
    const sidebarContent = (
        <>
            <div className="p-3 border-b border-slate-700/50 flex-shrink-0">
                <div className="flex items-center justify-between mb-2">
                    <h1 className="text-sm font-bold text-white">R-2 Parcels</h1>
                    <div className="flex gap-2 text-xs text-slate-400">
                        <span className="text-emerald-400">{stats.yes}y</span>
                        <span className="text-amber-400">{stats.maybe}m</span>
                        <span className="text-red-400">{stats.no}n</span>
                        <span>{stats.rated}/{stats.total}</span>
                    </div>
                </div>
                <div className="flex gap-2">
                    <div className="flex-1 relative">
                        <Search size={14} className="absolute left-2.5 top-2 text-slate-500" />
                        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..."
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
                    </div>
                    <select value={filterRating} onChange={e => setFilterRating(e.target.value)}
                        className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none">
                        <option value="all">All</option>
                        <option value="unrated">Unrated</option>
                        <option value="yes">Yes ({stats.yes})</option>
                        <option value="maybe">Maybe ({stats.maybe})</option>
                        <option value="no">No ({stats.no})</option>
                    </select>
                </div>
                {isDraggable && <div className="mt-2 text-[10px] text-slate-500 flex items-center gap-1"><GripVertical size={10} /> Drag to reorder</div>}
            </div>
            <div className="flex-1 overflow-y-auto">
                {isDraggable ? (
                    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                        <SortableContext items={filtered.map(p => p.id)} strategy={verticalListSortingStrategy}>
                            {filtered.map((p, i) => (
                                <SortableParcelCard key={p.id} parcel={p} isSelected={selectedId === p.id} rank={i + 1}
                                    onSelect={() => selectParcel(p.id)} />
                            ))}
                        </SortableContext>
                    </DndContext>
                ) : (
                    filtered.map(p => (
                        <StaticParcelCard key={p.id} parcel={p} isSelected={selectedId === p.id}
                            onSelect={() => selectParcel(p.id)} />
                    ))
                )}
            </div>
        </>
    );

    // ── Shared detail content ──
    const detailContent = d && !detailLoading ? (
        <div className="p-4 space-y-4">
            <div>
                <div className="flex items-center gap-2 mb-1">
                    <h2 className="text-lg font-bold text-white">{d.address || 'No address'}</h2>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${gradeColor(d.duplex_friendliness)}`}>{d.duplex_friendliness}</span>
                </div>
                <div className="text-xs text-slate-400">{d.parcel_id}</div>
                <div className="text-xs text-slate-500 mt-1">{d.owner_name}{d.owner_name_2 ? ` & ${d.owner_name_2}` : ''}</div>
                <div className="text-xs text-slate-600">{d.owner_mailing}</div>
            </div>

            {/* Owner Contact Info */}
            {d.owner_detail && d.owner_detail.skip_traced && (
                <div className="bg-slate-800/80 rounded-lg p-3 space-y-1.5">
                    <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Contact Info</div>
                    {d.owner_detail.phone_1 && (
                        <div className="flex items-center gap-2">
                            <a href={`tel:${d.owner_detail.phone_1}`} className="text-sm font-medium text-blue-400 hover:underline">{d.owner_detail.phone_1}</a>
                            <span className="text-[10px] text-slate-500">{d.owner_detail.phone_1_type}</span>
                        </div>
                    )}
                    {d.owner_detail.phone_2 && (
                        <div className="flex items-center gap-2">
                            <a href={`tel:${d.owner_detail.phone_2}`} className="text-xs text-blue-400/70 hover:underline">{d.owner_detail.phone_2}</a>
                            <span className="text-[10px] text-slate-600">{d.owner_detail.phone_2_type}</span>
                        </div>
                    )}
                    {d.owner_detail.email_1 && (
                        <div><a href={`mailto:${d.owner_detail.email_1}`} className="text-xs text-blue-400 hover:underline">{d.owner_detail.email_1}</a></div>
                    )}
                    {d.owner_detail.email_2 && (
                        <div><a href={`mailto:${d.owner_detail.email_2}`} className="text-xs text-blue-400/70 hover:underline">{d.owner_detail.email_2}</a></div>
                    )}
                    {!d.owner_detail.phone_1 && !d.owner_detail.email_1 && (
                        <div className="text-xs text-slate-600">No contact info found</div>
                    )}
                </div>
            )}

            <div className="flex gap-2 flex-wrap">
                {d.lat && d.lon && (
                    <>
                        <a href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${d.lat},${d.lon}&heading=0&pitch=0&fov=90`}
                           target="_blank" className="flex-1 min-w-[100px] flex items-center justify-center gap-1 bg-slate-800 border border-slate-700 rounded-lg py-2 text-xs text-slate-300 hover:bg-slate-700 active:bg-slate-600 transition">
                            <MapPin size={12} /> Street View
                        </a>
                        <a href={`https://www.google.com/maps/@${d.lat},${d.lon},18z/data=!3m1!1e1`}
                           target="_blank" className="flex-1 min-w-[100px] flex items-center justify-center gap-1 bg-slate-800 border border-slate-700 rounded-lg py-2 text-xs text-slate-300 hover:bg-slate-700 active:bg-slate-600 transition">
                            <ExternalLink size={12} /> Maps
                        </a>
                    </>
                )}
                {d.assessor_link && (
                    <a href={d.assessor_link} target="_blank" className="flex-1 min-w-[100px] flex items-center justify-center gap-1 bg-slate-800 border border-slate-700 rounded-lg py-2 text-xs text-slate-300 hover:bg-slate-700 active:bg-slate-600 transition">
                        <ExternalLink size={12} /> Assessor
                    </a>
                )}
            </div>

            <div>
                <div className="grid grid-cols-4 gap-1.5 mb-2">
                    {RATING_BUTTONS.map(r => (
                        <button key={r.value} onClick={() => handleRate(r.value)} disabled={saving}
                            className={`py-2 rounded-lg text-xs font-semibold text-white transition ${ratingState === r.value ? r.activeCls : r.cls} ${saving ? 'opacity-50' : ''}`}>
                            {r.label}
                        </button>
                    ))}
                </div>
                <textarea value={notesState} onChange={e => setNotesState(e.target.value)} onBlur={handleNotesSave}
                    placeholder="Notes..." rows={2}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none" />
            </div>

            <div className="grid grid-cols-3 gap-2 text-center">
                <Metric label="Appraised" value={fmt(d.appraised_value)} />
                <Metric label="Land Est" value={fmt(d.land_est_value)} accent="emerald" />
                <Metric label="ARV" value={fmt(d.arv_comp_median)} accent="blue" />
                <Metric label="Acres" value={d.computed_acres?.toFixed(2) || '-'} />
                <Metric label="Compact" value={d.compactness?.toFixed(2) || '-'} />
                <Metric label="Duplex %" value={d.duplex_ratio?.toFixed(1) + '%' || '-'} />
            </div>

            {d.owner_adjacent && (
                <div className={`rounded-lg p-3 text-xs ${d.owner_lives_adjacent ? 'bg-red-500/10 border border-red-500/30' : 'bg-amber-500/10 border border-amber-500/30'}`}>
                    <div className={`font-semibold mb-1 ${d.owner_lives_adjacent ? 'text-red-300' : 'text-amber-300'}`}>
                        {d.owner_lives_adjacent ? 'Owner Lives Next Door' : 'Owner Has Adjacent Parcel'}
                    </div>
                    <div className="text-slate-400">{d.adjacent_details}</div>
                </div>
            )}
            {!d.owner_adjacent && (
                <div className="rounded-lg p-3 text-xs bg-emerald-500/10 border border-emerald-500/30">
                    <div className="font-semibold text-emerald-300">Standalone Parcel</div>
                    <div className="text-slate-400">No adjacent parcels owned by the same person</div>
                </div>
            )}

            <DetailSection title="Utilities">
                <Row label="Water" value={d.water_provider || 'None'} />
                <Row label="Sewer" value={d.sewer_provider || 'None'} />
                <Row label="Score" value={d.utilities_score || '-'} />
            </DetailSection>

            <DetailSection title="Nearby Residential (0.25mi)">
                <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    <div><div className="text-lg font-bold text-slate-300">{d.nearby_sfr}</div><div className="text-slate-600">SFR</div></div>
                    <div><div className="text-lg font-bold text-emerald-400">{d.nearby_duplex}</div><div className="text-slate-600">Duplex</div></div>
                    <div><div className="text-lg font-bold text-blue-400">{d.nearby_triplex}</div><div className="text-slate-600">Tri</div></div>
                    <div><div className="text-lg font-bold text-purple-400">{d.nearby_quad}</div><div className="text-slate-600">Quad</div></div>
                </div>
            </DetailSection>

            <DetailSection title={`Land Comps (${d.land_comp_count}, ${d.land_comp_radius})`}>
                <Row label="Est. Value" value={fmt(d.land_est_value)} accent />
                <Row label="Range" value={`${fmt(d.land_comp_min)} - ${fmt(d.land_comp_max)}`} />
                <Row label="Median" value={fmt(d.land_comp_median)} />
                <Row label="Avg $/Acre" value={fmt(d.land_comp_avg_ppa)} />
                {d.land_comp_details && <div className="text-[10px] text-slate-600 bg-slate-800/50 rounded p-2 mt-2 leading-relaxed">{d.land_comp_details}</div>}
            </DetailSection>

            <DetailSection title={`ARV Comps (${d.arv_comp_count}, ${d.arv_comp_radius})`}>
                <Row label="ARV Median" value={fmt(d.arv_comp_median)} accent />
                <Row label="Range" value={`${fmt(d.arv_comp_min)} - ${fmt(d.arv_comp_max)}`} />
                {d.arv_comp_details && <div className="text-[10px] text-slate-600 bg-slate-800/50 rounded p-2 mt-2 leading-relaxed">{d.arv_comp_details}</div>}
            </DetailSection>

            <DetailSection title="Last Sale">
                <Row label="Price" value={fmt(d.last_sale_price)} />
                <Row label="Date" value={d.last_sale_date || '-'} />
            </DetailSection>
        </div>
    ) : detailLoading ? (
        <div className="flex items-center justify-center h-32 text-slate-500">Loading...</div>
    ) : null;

    return (
        <div className="h-[100dvh] w-screen flex overflow-hidden bg-slate-900">

            {/* ══════ DESKTOP: Side panels ══════ */}

            {/* Desktop sidebar */}
            <div className={`hidden lg:flex flex-col bg-slate-900/95 backdrop-blur border-r border-slate-700/50 transition-all duration-300 ${sidebarOpen ? 'w-[380px]' : 'w-0'} overflow-hidden`}>
                {sidebarContent}
            </div>

            {/* Desktop sidebar toggle */}
            <button onClick={() => setSidebarOpen(!sidebarOpen)}
                className="hidden lg:block absolute top-1/2 -translate-y-1/2 z-[1000] bg-slate-800/90 text-white p-1.5 rounded-r-lg border border-l-0 border-slate-600 hover:bg-slate-700 transition-all"
                style={{ left: sidebarOpen ? '380px' : '0px' }}>
                {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
            </button>

            {/* ══════ MAP (always full) ══════ */}
            <div className="flex-1 relative">
                <ParcelMapFull
                    parcels={filtered}
                    selectedId={selectedId}
                    onParcelClick={selectParcel}
                    detailRings={detail?.geometry_rings}
                    detailLat={detail?.lat}
                    detailLon={detail?.lon}
                />

                {/* Legend - bottom left on desktop, top left on mobile */}
                <div className="absolute bottom-4 left-4 lg:bottom-4 lg:left-4 z-[1000] bg-slate-900/85 backdrop-blur rounded-lg px-3 py-2 text-xs text-slate-300 space-y-0.5">
                    <div className="font-semibold text-white mb-1">Parcels ({filtered.length})</div>
                    <div><span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 mr-1.5" />Yes ({stats.yes})</div>
                    <div><span className="inline-block w-2.5 h-2.5 rounded-full bg-amber-500 mr-1.5" />Maybe ({stats.maybe})</div>
                    <div><span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500 mr-1.5" />No ({stats.no})</div>
                    <div><span className="inline-block w-2.5 h-2.5 rounded-full bg-purple-500 mr-1.5" />Unrated ({stats.total - stats.rated})</div>
                </div>

                {/* Desktop detail panel */}
                {d && (
                    <div className="hidden lg:block absolute top-0 right-0 z-[1000] h-full w-[420px] bg-slate-900/95 backdrop-blur border-l border-slate-700/50 overflow-y-auto">
                        <button onClick={() => { setSelectedId(null); setDetail(null); }}
                            className="absolute top-3 right-3 z-10 text-slate-400 hover:text-white">
                            <X size={18} />
                        </button>
                        {detailContent}
                    </div>
                )}
            </div>

            {/* ══════ MOBILE: Bottom sheets + FAB ══════ */}

            {/* Mobile FAB - list toggle */}
            <button onClick={() => setMobileSheet(mobileSheet === 'list' ? 'none' : 'list')}
                className="lg:hidden fixed bottom-6 right-6 z-[1100] bg-slate-800 text-white p-4 rounded-full shadow-xl border border-slate-600 active:bg-slate-700">
                <List size={22} />
            </button>

            {/* Mobile list bottom sheet */}
            <div className={`lg:hidden fixed inset-x-0 bottom-0 z-[1200] bg-slate-900/98 backdrop-blur border-t border-slate-700 rounded-t-2xl transition-transform duration-300 ${
                mobileSheet === 'list' ? 'translate-y-0' : 'translate-y-full'
            }`} style={{ height: '70dvh' }}>
                {/* Handle bar */}
                <div className="flex justify-center py-2">
                    <div className="w-10 h-1 rounded-full bg-slate-600" />
                </div>
                <div className="flex justify-between items-center px-4 pb-2">
                    <span className="text-sm font-bold text-white">Parcels</span>
                    <button onClick={() => setMobileSheet('none')} className="text-slate-400 p-1">
                        <X size={18} />
                    </button>
                </div>
                <div className="flex flex-col h-[calc(100%-3rem)] overflow-hidden">
                    {sidebarContent}
                </div>
            </div>

            {/* Mobile detail bottom sheet */}
            <div className={`lg:hidden fixed inset-x-0 bottom-0 z-[1300] bg-slate-900/98 backdrop-blur border-t border-slate-700 rounded-t-2xl transition-transform duration-300 ${
                mobileSheet === 'detail' && d ? 'translate-y-0' : 'translate-y-full'
            }`} style={{ height: '45dvh' }}>
                {/* Handle bar */}
                <div className="flex justify-center py-2">
                    <div className="w-10 h-1 rounded-full bg-slate-600" />
                </div>
                <div className="flex justify-between items-center px-4 pb-2">
                    <span className="text-sm font-bold text-white">{d?.address || 'Details'}</span>
                    <button onClick={() => setMobileSheet('none')} className="text-slate-400 p-1">
                        <X size={18} />
                    </button>
                </div>
                <div className="overflow-y-auto h-[calc(100%-3rem)]">
                    {detailContent}
                </div>
            </div>

            {/* Mobile backdrop */}
            {mobileSheet !== 'none' && (
                <div className="lg:hidden fixed inset-0 z-[1100] bg-black/40" onClick={() => setMobileSheet('none')} />
            )}
        </div>
    );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
    const colorMap: Record<string, string> = { emerald: 'text-emerald-400', blue: 'text-blue-400' };
    return (
        <div className="bg-slate-800/60 rounded-lg py-2 px-1">
            <div className={`text-sm font-bold ${accent ? colorMap[accent] : 'text-white'}`}>{value}</div>
            <div className="text-[10px] text-slate-500">{label}</div>
        </div>
    );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div>
            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">{title}</div>
            {children}
        </div>
    );
}

function Row({ label, value, accent }: { label: string; value: string | React.ReactNode; accent?: boolean }) {
    return (
        <div className="flex justify-between items-center py-1 text-xs">
            <span className="text-slate-500">{label}</span>
            <span className={`font-medium ${accent ? 'text-emerald-400' : 'text-slate-300'}`}>{value}</span>
        </div>
    );
}
