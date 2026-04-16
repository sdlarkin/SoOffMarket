'use client';

import dynamic from 'next/dynamic';

const ParcelDetailMapInner = dynamic(
    () => import('@/components/ParcelMap').then(mod => ({ default: mod.ParcelDetailMap })),
    { ssr: false }
);

interface Props {
    lat: number;
    lon: number;
    rings: number[][][];
    height?: string;
}

export default function ParcelDetailMapWrapper({ lat, lon, rings, height }: Props) {
    return <ParcelDetailMapInner lat={lat} lon={lon} rings={rings} height={height} />;
}
