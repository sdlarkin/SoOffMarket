import Link from 'next/link';
import { fetchDealsBuyer } from '@/lib/api';
import { ArrowLeft } from 'lucide-react';

export default async function BuyerDealsPage({ params }: { params: Promise<{ buyer: string }> }) {
    const { buyer: buyerSlug } = await params;
    const data = await fetchDealsBuyer(buyerSlug);

    return (
        <div className="min-h-screen bg-slate-900 text-white">
            <div className="max-w-4xl mx-auto px-6 py-12">
                <Link href="/deals" className="text-sm text-blue-400 hover:underline flex items-center gap-1 mb-6">
                    <ArrowLeft size={14} /> All Buyers
                </Link>

                <h1 className="text-3xl font-bold mb-1">{data.buyer.name}</h1>
                {data.buyer.company_name && (
                    <p className="text-slate-400 mb-8">{data.buyer.company_name}</p>
                )}
                {!data.buyer.company_name && <div className="mb-8" />}

                <h2 className="text-lg font-semibold text-slate-300 mb-4">Buy Boxes</h2>

                {data.buyboxes.length === 0 ? (
                    <div className="text-slate-500 text-center py-12">No active searches.</div>
                ) : (
                    <div className="grid gap-4">
                        {data.buyboxes.map(bb => (
                            <Link key={bb.id} href={`/deals/${buyerSlug}/${bb.slug}`}>
                                <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 hover:border-slate-500 transition-colors cursor-pointer">
                                    <div className="flex items-center justify-between mb-3">
                                        <h3 className="text-lg font-semibold">{bb.asset_type}</h3>
                                        <div className="text-right">
                                            <div className="text-2xl font-bold text-emerald-400">{bb.parcel_count}</div>
                                            <div className="text-xs text-slate-500">parcels</div>
                                        </div>
                                    </div>
                                    <div className="flex gap-3 text-sm text-slate-400">
                                        <span>{bb.target_states}</span>
                                        <span className="text-slate-600">|</span>
                                        <span>{bb.price_range}</span>
                                    </div>
                                </div>
                            </Link>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
