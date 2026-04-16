'use client';

import { MapContainer, TileLayer, CircleMarker, Polygon, Tooltip, useMap } from 'react-leaflet';
import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import type { ParcelOverview } from '@/lib/api';

function getColor(p: ParcelOverview): string {
    const rating = p.rating || '';
    if (rating === 'yes') return '#22c55e';
    if (rating === 'maybe') return '#f59e0b';
    if (rating === 'no') return '#ef4444';
    if (rating === 'skip') return '#64748b';
    return '#8b5cf6';
}

function getRadius(p: ParcelOverview, isSelected: boolean): number {
    if (isSelected) return 14;
    const acres = p.computed_acres || p.calc_acres || 0.5;
    return Math.max(7, Math.min(16, acres * 9));
}

function fmt(val: number | null | undefined): string {
    if (!val) return '?';
    return '$' + val.toLocaleString();
}

function FitBounds({ parcels }: { parcels: ParcelOverview[] }) {
    const map = useMap();
    const fitted = useRef(false);
    useEffect(() => {
        if (fitted.current || parcels.length === 0) return;
        const valid = parcels.filter(p => p.lat && p.lon);
        if (valid.length === 0) return;
        const bounds = L.latLngBounds(valid.map(p => [p.lat!, p.lon!] as [number, number]));
        map.fitBounds(bounds, { padding: [60, 60] });
        fitted.current = true;
    }, [parcels, map]);
    return null;
}

function FlyToSelected({ lat, lon }: { lat?: number | null; lon?: number | null }) {
    const map = useMap();
    useEffect(() => {
        if (!lat || !lon) return;
        const isMobile = window.innerWidth < 1024;
        if (isMobile) {
            const targetPoint = map.project([lat, lon], 17);
            const mapHeight = map.getSize().y;
            const offsetPoint = L.point(targetPoint.x, targetPoint.y + mapHeight * 0.3);
            const offsetLatLng = map.unproject(offsetPoint, 17);
            map.flyTo(offsetLatLng, 17, { duration: 0.6 });
        } else {
            map.flyTo([lat, lon], 17, { duration: 0.8 });
        }
    }, [lat, lon, map]);
    return null;
}

interface ParcelMapFullProps {
    parcels: ParcelOverview[];
    selectedId: string | null;
    onParcelClick: (id: string) => void;
    detailRings?: number[][][];
    detailLat?: number | null;
    detailLon?: number | null;
}

export default function ParcelMapFull({ parcels, selectedId, onParcelClick, detailRings, detailLat, detailLon }: ParcelMapFullProps) {
    // Guard against React Strict Mode double-mount crashing Leaflet
    const [mounted, setMounted] = useState(false);
    useEffect(() => { setMounted(true); }, []);
    if (!mounted) return <div style={{ height: '100%', width: '100%', background: '#0f172a' }} />;

    return (
        <MapContainer
            center={[35.05, -85.15]}
            zoom={11}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom
            zoomControl={false}
        >
            <TileLayer
                attribution="Esri"
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                maxZoom={20}
            />
            <TileLayer
                url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"
                maxZoom={20}
                opacity={0.6}
            />

            <FitBounds parcels={parcels} />
            {selectedId && <FlyToSelected lat={detailLat} lon={detailLon} />}

            {detailRings && detailRings.length > 0 && (
                <Polygon
                    positions={detailRings as [number, number][][]}
                    pathOptions={{ color: '#e94560', weight: 3, fillColor: '#e94560', fillOpacity: 0.3 }}
                />
            )}

            {parcels.map(p => {
                if (!p.lat || !p.lon) return null;
                const isSelected = p.id === selectedId;
                const color = getColor(p);
                return (
                    <CircleMarker
                        key={p.id}
                        center={[p.lat, p.lon]}
                        radius={getRadius(p, isSelected)}
                        pathOptions={{
                            color: isSelected ? '#e94560' : '#fff',
                            weight: isSelected ? 3 : 1.5,
                            fillColor: color,
                            fillOpacity: isSelected ? 1 : 0.85,
                        }}
                        eventHandlers={{ click: () => onParcelClick(p.id) }}
                    >
                        <Tooltip direction="top" offset={[0, -8]}>
                            <div className="text-xs">
                                <strong>{p.address || p.parcel_id}</strong><br />
                                {(p.computed_acres || p.calc_acres)?.toFixed(2)}ac | {fmt(p.appraised_value)} | Grade {p.duplex_friendliness}
                            </div>
                        </Tooltip>
                    </CircleMarker>
                );
            })}
        </MapContainer>
    );
}
