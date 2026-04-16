import Link from 'next/link';
import { fetchDealsIndex } from '@/lib/api';

export default async function DealsPage() {
    const buyers = await fetchDealsIndex();

    return (
        <div className="min-h-screen bg-slate-900 text-white">
            <div className="max-w-4xl mx-auto px-6 py-12">
                <h1 className="text-3xl font-bold mb-2">Deal Searches</h1>
                <p className="text-slate-400 mb-8">Active property searches for buyers</p>

                {buyers.length === 0 ? (
                    <div className="text-slate-500 text-center py-12">No active deal searches yet.</div>
                ) : (
                    <div className="grid gap-4">
                        {buyers.map(buyer => (
                            <Link key={buyer.id} href={`/deals/${buyer.slug}`}>
                                <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 hover:border-slate-500 transition-colors cursor-pointer">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h2 className="text-xl font-semibold">{buyer.name}</h2>
                                            {buyer.company_name && (
                                                <p className="text-sm text-slate-400">{buyer.company_name}</p>
                                            )}
                                        </div>
                                        <div className="text-right">
                                            <div className="text-2xl font-bold text-emerald-400">{buyer.buybox_count}</div>
                                            <div className="text-xs text-slate-500">parcels</div>
                                        </div>
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
