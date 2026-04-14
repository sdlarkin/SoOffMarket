'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { fetchFunnel, FunnelData, ResultData } from '../../../lib/api';
import Hero from '../../../components/Hero';
import ValueProp from '../../../components/ValueProp';
import Credibility from '../../../components/Credibility';
import AssessmentForm from '../../../components/AssessmentForm';
import ResultsView from '../../../components/ResultsView';
import { motion, AnimatePresence } from 'framer-motion';

export default function FunnelPage() {
    const { slug } = useParams();
    const [funnel, setFunnel] = useState<FunnelData | null>(null);
    const [view, setView] = useState<'LANDING' | 'ASSESSMENT' | 'RESULTS'>('LANDING');
    const [results, setResults] = useState<ResultData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (slug) {
            fetchFunnel(slug as string)
                .then(setFunnel)
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        }
    }, [slug]);

    if (loading) return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
    );

    if (!funnel) return (
        <div className="min-h-screen flex items-center justify-center">
            <h1 className="text-2xl font-bold text-gray-400">Funnel not found</h1>
        </div>
    );

    const handleComplete = (data: ResultData) => {
        setResults(data);
        setView('RESULTS');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    return (
        <main className="min-h-screen bg-white">
            <AnimatePresence mode="wait">
                {view === 'LANDING' && (
                    <motion.div
                        key="landing"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                    >
                        <Hero
                            hook={funnel.landing_page.hero_hook_frustration} // Default to frustration variant
                            subheading={funnel.landing_page.hero_subheading}
                            ctaText={funnel.landing_page.cta_text}
                            microcopy={funnel.landing_page.cta_microcopy}
                            onStart={() => setView('ASSESSMENT')}
                        />
                        <ValueProp areas={[
                            funnel.landing_page.value_prop_area_1,
                            funnel.landing_page.value_prop_area_2,
                            funnel.landing_page.value_prop_area_3
                        ]} />
                        <Credibility
                            bioName={funnel.landing_page.bio_name}
                            bioRole={funnel.landing_page.bio_role}
                            bioText={funnel.landing_page.bio_text}
                            researchText={funnel.landing_page.research_text}
                            stats={funnel.landing_page.stats_json}
                        />
                        {/* Final CTA block */}
                        <section className="py-20 text-center bg-blue-50">
                            <h3 className="text-3xl font-bold mb-8">Ready to discover your score?</h3>
                            <button
                                onClick={() => setView('ASSESSMENT')}
                                className="px-10 py-5 bg-blue-600 text-white text-xl font-bold rounded-full shadow-lg hover:bg-blue-700 transition-all"
                            >
                                Start the Assessment
                            </button>
                        </section>
                    </motion.div>
                )}

                {view === 'ASSESSMENT' && (
                    <motion.div
                        key="assessment"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0 }}
                        className="py-20 px-4 min-h-screen"
                    >
                        <AssessmentForm
                            funnelId={funnel.id}
                            questions={funnel.questions}
                            onComplete={handleComplete}
                        />
                    </motion.div>
                )}

                {view === 'RESULTS' && results && (
                    <motion.div
                        key="results"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="min-h-screen"
                    >
                        <ResultsView results={results} />
                    </motion.div>
                )}
            </AnimatePresence>
        </main>
    );
}
