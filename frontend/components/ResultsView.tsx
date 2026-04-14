import { motion } from 'framer-motion';
import { ResultData } from '../lib/api';
import { Award, Target, Zap, ExternalLink, Calendar, PlayCircle } from 'lucide-react';

interface ResultsViewProps {
    results: ResultData;
}

export default function ResultsView({ results }: ResultsViewProps) {
    const { score, tier, insights, next_step_type } = results;

    const getTierColor = (label: string) => {
        switch (label.toLowerCase()) {
            case 'hot': return 'text-orange-600 bg-orange-50 border-orange-200';
            case 'warm': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
            default: return 'text-blue-600 bg-blue-50 border-blue-200';
        }
    };

    const getCTA = () => {
        if (next_step_type === 'High Qualified') {
            return {
                icon: <Calendar className="w-6 h-6" />,
                title: "Book a 1:1 Strategy Session",
                desc: "You're ready for high-level support. Let's build your plan together.",
                button: "Schedule Now"
            };
        } else if (next_step_type === 'Moderately Qualified') {
            return {
                icon: <PlayCircle className="w-6 h-6" />,
                title: "Join Our Next Live Training",
                desc: "Perfect for where you are. See how to bridge the final gaps.",
                button: "Register for Webinar"
            };
        } else {
            return {
                icon: <ExternalLink className="w-6 h-6" />,
                title: "Explore Our Resource Library",
                desc: "Start with these foundations to see quick improvements.",
                button: "Watch Foundation Video"
            };
        }
    };

    const cta = getCTA();

    return (
        <div className="max-w-4xl mx-auto py-12 px-4">
            <section className="text-center mb-16">
                <h2 className="text-4xl font-bold text-gray-900 mb-8">The Results Are In...</h2>

                <div className="relative inline-block mb-8">
                    <svg className="w-64 h-64">
                        <circle
                            cx="128" cy="128" r="110"
                            fill="none"
                            stroke="#F3F4F6"
                            strokeWidth="20"
                        />
                        <motion.circle
                            cx="128" cy="128" r="110"
                            fill="none"
                            stroke="#2563EB"
                            strokeWidth="20"
                            strokeDasharray="691"
                            initial={{ strokeDashoffset: 691 }}
                            animate={{ strokeDashoffset: 691 - (691 * score) / 100 }}
                            transition={{ duration: 1.5, ease: "easeOut" }}
                            strokeLinecap="round"
                        />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-6xl font-black text-gray-900">{Math.round(score)}</span>
                        <span className="text-sm font-bold text-gray-400 uppercase tracking-widest">Score / 100</span>
                    </div>
                </div>

                {tier && (
                    <div className={`inline-block px-6 py-2 rounded-full border ${getTierColor(tier.label)}`}>
                        <span className="text-xl font-bold">{tier.label} Category</span>
                    </div>
                )}

                {tier && (
                    <div className="mt-8 max-w-2xl mx-auto">
                        <h3 className="text-3xl font-bold text-gray-900 mb-4">{tier.headline}</h3>
                        <p className="text-lg text-gray-600 leading-relaxed">{tier.description}</p>
                    </div>
                )}
            </section>

            <section className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
                {insights.map((insight, index) => (
                    <div key={index} className="bg-white p-8 rounded-3xl shadow-sm border border-gray-100">
                        <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center mb-6">
                            {[<Award />, <Target />, <Zap />][index % 3]}
                        </div>
                        <h4 className="text-xl font-bold text-gray-900 mb-4">{insight.title}</h4>
                        <p className="text-gray-600 leading-relaxed">{insight.content}</p>
                    </div>
                ))}
            </section>

            <section className="bg-blue-600 rounded-[3rem] p-12 text-white shadow-2xl relative overflow-hidden">
                <div className="relative z-10">
                    <div className="flex items-center gap-4 mb-6">
                        <div className="p-3 bg-white/20 rounded-xl backdrop-blur-sm">
                            {cta.icon}
                        </div>
                        <span className="text-blue-100 font-bold tracking-widest uppercase text-sm">Recommended Next Step</span>
                    </div>
                    <h3 className="text-3xl md:text-4xl font-black mb-4">{cta.title}</h3>
                    <p className="text-xl text-blue-100 mb-10 max-w-xl">{cta.desc}</p>
                    <button className="px-10 py-5 bg-white text-blue-600 text-lg font-black rounded-2xl shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all">
                        {cta.button}
                    </button>
                </div>
                <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
                <div className="absolute bottom-0 left-0 -ml-16 -mb-16 w-64 h-64 bg-black/10 rounded-full blur-3xl" />
            </section>
        </div>
    );
}
