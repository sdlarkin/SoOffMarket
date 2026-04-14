import { fetchMatchedPropertyDetails } from '@/lib/api';
import Link from 'next/link';
import { ArrowLeft, Building, MapPin, Users, Mail, Phone, BadgeDollarSign, HeartHandshake } from 'lucide-react';

export default async function MatchedPropertyDetail({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = await params;
    const property = await fetchMatchedPropertyDetails(resolvedParams.id);

    return (
        <div className="h-screen flex flex-col bg-slate-50 overflow-hidden">
            {/* Header Navbar */}
            <div className="bg-white border-b border-slate-200 px-8 py-4 shrink-0 flex items-center justify-between">
                <Link href="/properties-matched" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-900 font-semibold transition-colors">
                    <ArrowLeft size={20} /> Back to Pipeline
                </Link>
                <div className="flex items-center gap-3">
                    <span className="font-bold text-slate-800">Total Demand:</span>
                    <span className="bg-red-600 text-white px-4 py-1 rounded-full font-extrabold shadow-sm">
                        {property.match_count} Interested Buyers
                    </span>
                </div>
            </div>

            {/* Split Screen Layout */}
            <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
                
                {/* LEFT SIDE: Physical Property (Sticky Layout) */}
                <div className="w-full lg:w-[450xl] lg:max-w-xl bg-white border-r border-slate-200 overflow-y-auto p-8 lg:p-12">
                    <div className="mb-8">
                        <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center mb-6 shadow-sm ring-4 ring-blue-50">
                            <Building size={32} />
                        </div>
                        <h1 className="text-4xl font-black text-slate-900 leading-tight mb-4 tracking-tight">
                            {property.company_name}
                        </h1>
                        <p className="text-lg text-slate-500 font-medium flex items-center gap-2 p-4 bg-slate-50 rounded-2xl border border-slate-100">
                            <MapPin size={20} className="text-blue-500 shrink-0"/> 
                            <span>{property.address}, <br/>{property.city}, {property.state} {property.zip_code}</span>
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-10 border-t border-slate-100 pt-8 mt-8">
                        <div>
                            <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Asset Class</p>
                            <p className="font-bold text-slate-800">{property.industry || 'Unknown'}</p>
                        </div>
                        <div>
                            <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Scale</p>
                            <p className="font-bold text-slate-800">{property.employee_range || 'Unknown'} Emps</p>
                        </div>
                        <div className="col-span-2 mt-2">
                            <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Reported Revenue</p>
                            <p className="font-bold text-slate-800">{property.annual_sales || 'Undisclosed'}</p>
                        </div>
                    </div>

                    {/* Facility Contacts */}
                    <div>
                        <h3 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-2">
                            <Users size={20} className="text-slate-400"/> Facility Contacts
                        </h3>
                        <div className="space-y-4">
                            {property.contacts.map((contact: any, i: number) => (
                                <div key={i} className="bg-white border border-slate-200 p-5 rounded-2xl shadow-sm">
                                    <p className="font-extrabold text-slate-900 text-lg">{contact.first_name} {contact.last_name}</p>
                                    <p className="text-blue-600 font-semibold text-sm mb-3">{contact.title}</p>
                                    
                                    <div className="space-y-2 mt-4 pt-4 border-t border-slate-100">
                                        {contact.email && (
                                            <p className="text-slate-600 text-sm flex items-center gap-2 font-medium">
                                                <Mail size={14} className="text-slate-400"/> {contact.email}
                                            </p>
                                        )}
                                        {contact.direct_phone && (
                                            <p className="text-slate-600 text-sm flex items-center gap-2 font-medium">
                                                <Phone size={14} className="text-slate-400"/> {contact.direct_phone}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            ))}
                            {property.contacts.length === 0 && (
                                <p className="text-slate-500 italic p-4 bg-slate-50 rounded-xl">No specific employee contacts listed.</p>
                            )}
                        </div>
                    </div>
                </div>

                {/* RIGHT SIDE: Scrollable List of Buyers */}
                <div className="flex-1 bg-slate-50 overflow-y-auto p-8 lg:p-12 relative">
                    <div className="max-w-4xl mx-auto">
                        <div className="mb-8">
                            <h2 className="text-2xl font-extrabold text-slate-900 mb-2">Interested Buyers Feed</h2>
                            <p className="text-slate-500">Scroll to view all {property.match_count} investors whose BuyBox matched this address.</p>
                        </div>

                        <div className="space-y-6">
                            {property.buyer_matches.map((match: any, index: number) => {
                                const box = match.buybox;
                                return (
                                    <div key={match.id} className="bg-white p-8 rounded-3xl border border-slate-200 shadow-md hover:border-slate-300 transition-colors relative overflow-hidden">
                                        <div className="absolute top-0 left-0 w-2 h-full bg-emerald-500"></div>
                                        
                                        <div className="flex flex-col md:flex-row justify-between mb-6 pb-6 border-b border-slate-100 gap-6">
                                            <div>
                                                <p className="text-emerald-600 font-bold uppercase tracking-wider text-xs mb-1">Intent Buyer</p>
                                                <h3 className="text-2xl font-black text-slate-900">{box.buyer.name}</h3>
                                                {box.buyer.company_name && (
                                                    <p className="text-slate-500 font-medium">{box.buyer.company_name}</p>
                                                )}
                                            </div>
                                            <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 max-w-sm">
                                                <p className="text-xs text-slate-400 font-bold uppercase mb-1">Target States Overview</p>
                                                <p className="font-semibold text-slate-800 line-clamp-2" title={box.target_states}>
                                                    {box.target_states}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                            <div>
                                                <div className="flex items-center gap-2 text-slate-400 mb-2">
                                                    <BadgeDollarSign size={16}/> <span className="font-bold uppercase text-xs">Acquisition Capital</span>
                                                </div>
                                                <p className="font-bold text-slate-900 bg-emerald-50 py-2 px-4 rounded-lg inline-block text-emerald-800">
                                                    {box.price_range || 'Not Specified'}
                                                </p>
                                            </div>
                                            <div>
                                                <div className="flex items-center gap-2 text-slate-400 mb-2">
                                                    <HeartHandshake size={16}/> <span className="font-bold uppercase text-xs">Ideal Structure</span>
                                                </div>
                                                <p className="font-medium text-slate-700">
                                                    {box.deal_structures || 'Cash / Conventional'}
                                                </p>
                                            </div>
                                        </div>

                                        {box.strategy_notes && (
                                            <div className="mt-6 pt-6 border-t border-slate-100">
                                                <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-2">Internal Strategy Notes</p>
                                                <p className="text-slate-600 bg-slate-50 p-4 rounded-xl text-sm italic border border-slate-100">
                                                    "{box.strategy_notes}"
                                                </p>
                                            </div>
                                        )}
                                        
                                        {/* Contact Badges */}
                                        <div className="mt-8 flex gap-3">
                                            {box.buyer.email && (
                                                <a href={`mailto:${box.buyer.email}`} className="bg-slate-900 hover:bg-slate-800 text-white px-4 py-2 rounded-full text-sm font-bold transition-colors shadow-md">
                                                    Email Investor
                                                </a>
                                            )}
                                            {box.buyer.phone && (
                                                <span className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-full text-sm font-bold flex items-center gap-2">
                                                    <Phone size={14}/> {box.buyer.phone}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        
                        {property.buyer_matches.length === 0 && (
                            <div className="bg-white rounded-3xl border-2 border-dashed border-slate-200 p-12 text-center">
                                <Users size={48} className="mx-auto text-slate-300 mb-4" />
                                <h3 className="text-xl font-bold text-slate-900 mb-2">No Buyers Validated</h3>
                                <p className="text-slate-500">There are currently no active BuyBoxes looking for this specific asset.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
