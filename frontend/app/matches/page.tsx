import { fetchMatches } from '@/lib/api';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';

export default async function MatchesList({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
    // Await the searchParams promise to extract 'page'
    const sp = await searchParams;
    const page = parseInt(sp.page || '1');
    const data = await fetchMatches(page);

    return (
        <div className="max-w-5xl mx-auto py-12 px-6">
            <div className="flex items-center justify-between mb-10">
                <div>
                    <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">Active Matches</h1>
                    <p className="text-slate-500 mt-2">Displaying 20 highly-correlated matches per page</p>
                </div>
                <div className="bg-blue-50 text-blue-700 px-4 py-2 rounded-full font-bold text-sm">
                    {data.count} Total Hits
                </div>
            </div>

            <div className="space-y-4">
                {data.results.map((match) => (
                    <Link href={`/matches/${match.id}`} key={match.id}>
                        <div className="group bg-white p-6 rounded-3xl border border-slate-100 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all flex items-center justify-between cursor-pointer">
                            <div className="flex gap-12">
                                {/* Property Info */}
                                <div>
                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Property</p>
                                    <h3 className="text-lg font-bold text-slate-900">{match.property_name}</h3>
                                    <span className="inline-block px-3 py-1 bg-red-50 text-red-700 font-bold text-xs rounded-full mt-2">
                                        {match.property_state}
                                    </span>
                                </div>
                                
                                {/* Buyer Info */}
                                <div>
                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Buyer</p>
                                    <h3 className="text-lg font-bold text-slate-900">{match.buyer_name}</h3>
                                    <span className="inline-block px-3 py-1 bg-emerald-50 text-emerald-700 font-bold text-xs rounded-full mt-2">
                                        {match.asset_type}
                                    </span>
                                </div>
                            </div>

                            <div className="flex items-center gap-6">
                                <div className="text-right hidden sm:block">
                                    <p className="text-sm font-semibold text-slate-600">{match.match_score}% Match</p>
                                </div>
                                <div className="w-12 h-12 rounded-full bg-slate-50 flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-colors text-slate-400">
                                    <ChevronRight />
                                </div>
                            </div>
                        </div>
                    </Link>
                ))}
            </div>

            {/* Pagination Controls */}
            <div className="flex items-center justify-center gap-6 mt-12">
                {data.previous && (
                    <Link href={`/matches?page=${page - 1}`} className="px-6 py-3 bg-white border border-slate-200 rounded-full font-semibold hover:bg-slate-50 transition-colors">
                        Previous Page
                    </Link>
                )}
                {data.next && (
                    <Link href={`/matches?page=${page + 1}`} className="px-6 py-3 bg-blue-600 text-white rounded-full font-bold hover:bg-blue-700 transition-colors shadow-lg shadow-blue-200">
                        Next Page
                    </Link>
                )}
            </div>
        </div>
    );
}
