'use client';

import dynamic from 'next/dynamic';
import type { ParcelOverview } from '@/lib/api';
import { useRouter } from 'next/navigation';

const ParcelMap = dynamic(() => import('@/components/ParcelMap'), { ssr: false });

export default function ParcelMapWrapper({ parcels }: { parcels: ParcelOverview[] }) {
    const router = useRouter();
    return (
        <ParcelMap
            parcels={parcels}
            height="45vh"
            onParcelClick={(id) => router.push(`/parcels/${id}`)}
        />
    );
}
