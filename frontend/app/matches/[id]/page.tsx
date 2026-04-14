import { fetchMatchDetails } from '@/lib/api';
import Link from 'next/link';
import { ArrowLeft, User, Building, MapPin, BadgeDollarSign, HeartHandshake } from 'lucide-react';

export default async function MatchDetail({ params }: { params: Promise<{ id: string }> }) {
    // Await the params promise to extract 'id'
    const resolvedParams = await params;
    const match = await fetchMatchDetails(resolvedParams.id);
    const property = match.property;
    const buybox = match.buybox;

    return (
        <div className="max-w-7xl mx-auto py-12 px-6">
            <Link href="/matches" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-900 font-semibold mb-8 transition-colors">
                <ArrowLeft size={20} /> Back to Matches
            </Link>

            <div className="bg-slate-900 rounded-3xl p-8 mb-8 text-white flex flex-col sm:flex-row items-center justify-between shadow-2xl">
                <div>
                    <h1 className="text-3xl font-extrabold flex items-center gap-4">
                        Match Correlated <span className="text-emerald-400">{match.match_score}%</span>
                    </h1>
                    <p className="text-slate-400 mt-2 max-w-2xl">{match.match_reason}</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                
                {/* LEFT SIDE: PROPERTY */}
                <div className="bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden">
                    <div className="bg-blue-50/50 border-b border-blue-100 p-8 flex items-start justify-between">
                        <div>
                            <p className="text-blue-600 font-bold tracking-wider text-sm mb-2 flex items-center gap-2"><Building size={16}/> TARGET PROPERTY</p>
                            <h2 className="text-3xl font-black text-slate-900">{property.company_name}</h2>
                            <p className="text-slate-500 mt-2 font-medium flex items-center gap-2"><MapPin size={16}/> {property.address}, {property.city}, {property.state} {property.zip_code}</p>
                        </div>
                        {/* Highlighting the exact state that triggered the match */}
                        <div className="px-4 py-2 bg-blue-600 text-white rounded-2xl font-black text-xl shadow-lg ring-4 ring-blue-100">
                            {property.state}
                        </div>
                    </div>

                    <div className="p-8 space-y-8">
                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <p className="text-xs text-slate-400 font-bold uppercase mb-1">Industry</p>
                                <p className="font-semibold">{property.industry || 'Unknown'}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-400 font-bold uppercase mb-1">Annual Sales</p>
                                <p className="font-semibold">{property.annual_sales || 'Unknown'}</p>
                            </div>
                        </div>

                        {/* Contacts Nested Loop */}
                        <div>
                            <h3 className="text-lg font-bold text-slate-900 border-b pb-4 mb-4">Property Contacts</h3>
                            <div className="space-y-4">
                                {property.contacts.map((contact: any, i: number) => (
                                    <div key={i} className="flex gap-4 items-center bg-slate-50 p-4 rounded-2xl">
                                        <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-bold">
                                            {contact.first_name[0]}{contact.last_name[0]}
                                        </div>
                                        <div>
                                            <p className="font-bold text-slate-900">{contact.first_name} {contact.last_name}</p>
                                            <p className="text-sm text-slate-500">{contact.title} &bull; {contact.email || contact.direct_phone}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* RIGHT SIDE: BUYER / BUYBOX */}
                <div className="bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden">
                    <div className="bg-emerald-50/50 border-b border-emerald-100 p-8 flex items-start justify-between">
                        <div>
                            <p className="text-emerald-600 font-bold tracking-wider text-sm mb-2 flex items-center gap-2"><User size={16}/> INTENT BUYER</p>
                            <h2 className="text-3xl font-black text-slate-900">{buybox.buyer.name}</h2>
                            <p className="text-slate-500 mt-2 font-medium">For {buybox.buyer.company_name || 'Independent Group'}</p>
                        </div>
                    </div>

                    <div className="p-8 space-y-8">
                        
                        <div className="bg-slate-900 text-white p-6 rounded-2xl relative overflow-hidden">
                            <MapPin className="absolute -right-6 -bottom-6 text-slate-800" size={120} />
                            <div className="relative z-10">
                                <p className="text-slate-400 text-sm font-bold uppercase mb-2">Target Acquisition States</p>
                                <p className="font-semibold text-lg leading-relaxed">{buybox.target_states}</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <p className="text-xs text-slate-400 font-bold uppercase mb-1 flex items-center gap-1"><BadgeDollarSign size={14}/> Price Range</p>
                                <p className="font-semibold">{buybox.price_range || 'Any'}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-400 font-bold uppercase mb-1 flex items-center gap-1"><HeartHandshake size={14}/> Deal Structure</p>
                                <p className="font-semibold">{buybox.deal_structures || 'Cash'}</p>
                            </div>
                        </div>

                        <div>
                            <h3 className="text-lg font-bold text-slate-900 border-b pb-4 mb-4">Investment Strategy</h3>
                            <div className="space-y-6">
                                <div>
                                    <p className="text-sm text-slate-500 font-bold mb-1">Property Types</p>
                                    <p className="text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-100">{buybox.property_types}</p>
                                </div>
                                {buybox.strategy_notes && (
                                    <div>
                                        <p className="text-sm text-slate-500 font-bold mb-1">Cheat Codes / Notes</p>
                                        <p className="text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-100">{buybox.strategy_notes}</p>
                                    </div>
                                )}
                            </div>
                        </div>

                    </div>
                </div>

            </div>
        </div>
    );
}
