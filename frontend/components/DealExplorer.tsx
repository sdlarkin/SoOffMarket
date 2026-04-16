'use client';

import { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { fetchDealsBuyBox, fetchDealsParcelDetail, rateParcel, reorderParcels } from '@/lib/api';
import type { ParcelOverview, ParcelDetail, DealsBuyBoxResponse } from '@/lib/api';
import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown, X, ExternalLink, MapPin, Search, GripVertical, List } from 'lucide-react';
import {
    DndContext, closestCenter, PointerSensor, TouchSensor, useSensor, useSensors,
    type DragEndEvent,
} from '@dnd-kit/core';
import {
    SortableContext, verticalListSortingStrategy, useSortable, arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

// Re-export everything from ParcelExplorer but with deals API
// This is a thin wrapper that swaps the data source

import ParcelExplorerBase from './ParcelExplorer';

interface DealExplorerProps {
    buyerSlug: string;
    buyboxSlug: string;
    buyerName: string;
    buyboxName: string;
}

export default function DealExplorer({ buyerSlug, buyboxSlug, buyerName, buyboxName }: DealExplorerProps) {
    // We reuse the same ParcelExplorer component but override the data fetching
    // by passing initial data and custom fetch functions
    return (
        <ParcelExplorerBase
            fetchOverview={async () => {
                const data = await fetchDealsBuyBox(buyerSlug, buyboxSlug);
                return data.parcels;
            }}
            fetchDetail={async (id: string) => {
                return fetchDealsParcelDetail(buyerSlug, buyboxSlug, id);
            }}
            title={`${buyerName} — ${buyboxName}`}
        />
    );
}
