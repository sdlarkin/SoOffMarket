interface CredibilityProps {
    bioName: string;
    bioRole: string;
    bioText: string;
    researchText: string;
    stats: string[];
}

export default function Credibility({ bioName, bioRole, bioText, researchText, stats }: CredibilityProps) {
    return (
        <section className="py-20 px-4 bg-gray-50">
            <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-16 items-start">
                <div>
                    <h2 className="text-3xl font-bold text-gray-900 mb-6">Created by {bioName}</h2>
                    <p className="text-blue-600 font-semibold mb-4">{bioRole}</p>
                    <div className="text-lg text-gray-700 leading-relaxed whitespace-pre-wrap">
                        {bioText}
                    </div>
                </div>
                <div className="bg-white p-8 rounded-3xl shadow-sm border border-gray-100">
                    <h3 className="text-2xl font-bold text-gray-900 mb-6">Background & Research</h3>
                    <p className="text-gray-600 mb-8 leading-relaxed">
                        {researchText}
                    </p>
                    <div className="space-y-4">
                        {stats.map((stat, index) => (
                            <div key={index} className="flex items-start gap-4">
                                <div className="w-6 h-6 bg-green-100 text-green-600 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                                    ✓
                                </div>
                                <p className="text-gray-900 font-medium italic">
                                    "{stat}"
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}
