'use client';

import { MapContainer, TileLayer, CircleMarker, Polygon, Tooltip, useMap } from 'react-leaflet';
import { useEffect } from 'react';
import type { ParcelOverview } from '@/lib/api';
import type { LatLngBoundsExpression } from 'leaflet';

function getColor(p: ParcelOverview): string {
    const grade = p.duplex_friendliness;
    const geo = p.geo_priority || '';
    if (geo.startsWith('1')) return grade === 'A' ? '#22c55e' : '#86efac';
    if (geo.startsWith('2')) return grade === 'A' ? '#3b82f6' : '#93c5fd';
    return grade === 'A' ? '#f59e0b' : '#fcd34d';
}

function getRadius(p: ParcelOverview): number {
    const acres = p.computed_acres || p.calc_acres || 0.5;
    return Math.max(8, Math.min(18, acres * 10));
}

function fmt(val: number | null | undefined): string {
    if (!val) return '?';
    return '$' + val.toLocaleString();
}

function FitBounds({ parcels }: { parcels: ParcelOverview[] }) {
    const map = useMap();
    useEffect(() => {
        const valid = parcels.filter(p => p.lat && p.lon);
        if (valid.length === 0) return;
        const bounds: LatLngBoundsExpression = valid.map(p => [p.lat!, p.lon!] as [number, number]);
        map.fitBounds(bounds, { padding: [50, 50] });
    }, [parcels, map]);
    return null;
}

interface ParcelMapProps {
    parcels: ParcelOverview[];
    onParcelClick?: (id: string) => void;
    height?: string;
}

export default function ParcelMap({ parcels, onParcelClick, height = '50vh' }: ParcelMapProps) {
    const center = parcels.length > 0 && parcels[0].lat
        ? [parcels[0].lat, parcels[0].lon!] as [number, number]
        : [35.05, -85.15] as [number, number];

    return (
        <MapContainer center={center} zoom={11} style={{ height, width: '100%' }} scrollWheelZoom>
            <TileLayer
                attribution="Esri"
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                maxZoom={20}
            />
            <TileLayer
                url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"
                maxZoom={20}
                opacity={0.7}
            />
            <FitBounds parcels={parcels} />
            {parcels.map(p => {
                if (!p.lat || !p.lon) return null;
                const color = getColor(p);
                return (
                    <CircleMarker
                        key={p.id}
                        center={[p.lat, p.lon]}
                        radius={getRadius(p)}
                        pathOptions={{ color: '#fff', weight: 2, fillColor: color, fillOpacity: 0.85 }}
                        eventHandlers={{
                            click: () => onParcelClick?.(p.id),
                        }}
                    >
                        <Tooltip direction="top" offset={[0, -8]}>
                            <div className="text-sm">
                                <strong>{p.address || p.parcel_id}</strong><br />
                                {p.computed_acres?.toFixed(2) || p.calc_acres}ac | {fmt(p.appraised_value)} | {p.duplex_friendliness}
                            </div>
                        </Tooltip>
                    </CircleMarker>
                );
            })}
        </MapContainer>
    );
}

// Detail map with parcel boundary polygon
interface ParcelDetailMapProps {
    lat: number;
    lon: number;
    rings: number[][][];
    height?: string;
}

export function ParcelDetailMap({ lat, lon, rings, height = '400px' }: ParcelDetailMapProps) {
    return (
        <MapContainer center={[lat, lon]} zoom={17} style={{ height, width: '100%' }} scrollWheelZoom>
            <TileLayer
                attribution="Esri"
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                maxZoom={20}
            />
            <TileLayer
                url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"
                maxZoom={20}
                opacity={0.7}
            />
            {rings.length > 0 && (
                <Polygon
                    positions={rings as [number, number][][]}
                    pathOptions={{ color: '#e94560', weight: 3, fillColor: '#e94560', fillOpacity: 0.25 }}
                />
            )}
        </MapContainer>
    );
}
