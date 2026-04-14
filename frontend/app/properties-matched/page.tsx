import { fetchMatchedProperties } from '@/lib/api';
import Link from 'next/link';
import { Building, MapPin, Users, ChevronRight } from 'lucide-react';

export default async function MatchedPropertiesList({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
    const sp = await searchParams;
    const page = parseInt(sp.page || '1');
    const data = await fetchMatchedProperties(page);

    return (
        <div className="max-w-6xl mx-auto py-12 px-6">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-10 gap-4">
                <div>
                    <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">Active Deal Pipeline</h1>
                    <p className="text-slate-500 mt-2 text-lg">Unique properties currently attracting buyer interest.</p>
                </div>
                <div className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-5 py-3 rounded-2xl font-bold flex items-center gap-2 shadow-sm">
                    <Building size={20} /> {data.count} Properties Listed
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {data.results.map((prop) => (
                    <Link href={`/properties-matched/${prop.id}`} key={prop.id}>
                        <div className="group bg-white p-6 rounded-3xl border border-slate-200 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all cursor-pointer h-full flex flex-col justify-between">
                            
                            <div>
                                <div className="flex items-start justify-between mb-4">
                                    <h3 className="text-xl font-bold text-slate-900 line-clamp-1">{prop.company_name}</h3>
                                    <div className="bg-blue-600 text-white w-10 h-10 rounded-full flex items-center justify-center font-black shadow-md shrink-0">
                                        {prop.state}
                                    </div>
                                </div>
                                <p className="text-slate-500 font-medium flex items-center gap-2 mb-2">
                                    <MapPin size={16}/> {prop.address}, {prop.city} {prop.zip_code}
                                </p>
                                <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">
                                    {prop.industry || 'Asset Class Unspecified'}
                                </p>
                            </div>

                            <div className="mt-8 pt-6 border-t border-slate-100 flex items-center justify-between">
                                <div className="flex items-center gap-3 bg-red-50 text-red-700 px-4 py-2 rounded-xl border border-red-100 group-hover:bg-red-600 group-hover:text-white transition-colors">
                                    <Users size={18} />
                                    <span className="font-extrabold">{prop.match_count} Buyers Match</span>
                                </div>
                                <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center group-hover:bg-slate-900 group-hover:text-white transition-colors text-slate-400">
                                    <ChevronRight size={20} />
                                </div>
                            </div>

                        </div>
                    </Link>
                ))}
            </div>

            {/* Pagination Controls */}
            <div className="flex items-center justify-center gap-6 mt-12">
                {data.previous && (
                    <Link href={`/properties-matched?page=${page - 1}`} className="px-6 py-3 bg-white border border-slate-200 rounded-full font-semibold hover:bg-slate-50 transition-colors">
                        Previous Page
                    </Link>
                )}
                {data.next && (
                    <Link href={`/properties-matched?page=${page + 1}`} className="px-6 py-3 bg-slate-900 text-white rounded-full font-bold hover:bg-slate-800 transition-colors shadow-lg">
                        Next Page
                    </Link>
                )}
            </div>
        </div>
    );
}
