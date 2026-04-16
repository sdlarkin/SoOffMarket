'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { rateParcel } from '@/lib/api';

interface ParcelRatingControlsProps {
    parcelId: string;
    currentRating?: string;
    currentNotes?: string;
}

const RATINGS = [
    { value: 'yes', label: 'Yes', color: 'bg-emerald-500 hover:bg-emerald-600', activeColor: 'bg-emerald-600 ring-2 ring-emerald-300' },
    { value: 'maybe', label: 'Maybe', color: 'bg-amber-500 hover:bg-amber-600', activeColor: 'bg-amber-600 ring-2 ring-amber-300' },
    { value: 'no', label: 'No', color: 'bg-red-500 hover:bg-red-600', activeColor: 'bg-red-600 ring-2 ring-red-300' },
    { value: 'skip', label: 'Skip', color: 'bg-slate-500 hover:bg-slate-600', activeColor: 'bg-slate-600 ring-2 ring-slate-300' },
];

export default function ParcelRatingControls({ parcelId, currentRating, currentNotes }: ParcelRatingControlsProps) {
    const router = useRouter();
    const [rating, setRating] = useState(currentRating || '');
    const [notes, setNotes] = useState(currentNotes || '');
    const [saving, setSaving] = useState(false);

    async function handleRate(value: string) {
        setSaving(true);
        try {
            await rateParcel(parcelId, { rating: value, notes });
            setRating(value);
            router.refresh();
        } catch (e) {
            console.error('Failed to save rating:', e);
        } finally {
            setSaving(false);
        }
    }

    async function handleNotesBlur() {
        if (!rating) return;
        setSaving(true);
        try {
            await rateParcel(parcelId, { rating, notes });
            router.refresh();
        } catch (e) {
            console.error('Failed to save notes:', e);
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="space-y-3">
            <div className="flex gap-2">
                {RATINGS.map(r => (
                    <button
                        key={r.value}
                        onClick={() => handleRate(r.value)}
                        disabled={saving}
                        className={`px-4 py-2 rounded-lg text-white font-semibold text-sm transition-all ${
                            rating === r.value ? r.activeColor : r.color
                        } ${saving ? 'opacity-50' : ''}`}
                    >
                        {r.label}
                    </button>
                ))}
            </div>
            <textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                onBlur={handleNotesBlur}
                placeholder="Notes about this parcel..."
                rows={3}
                className="w-full rounded-lg border border-slate-200 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
        </div>
    );
}
