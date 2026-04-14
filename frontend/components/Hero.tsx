import Link from 'next/link';

interface HeroProps {
    hook: string;
    subheading: string;
    ctaText: string;
    microcopy: string;
    onStart: () => void;
}

export default function Hero({ hook, subheading, ctaText, microcopy, onStart }: HeroProps) {
    return (
        <section className="relative py-20 px-4 text-center bg-gradient-to-b from-blue-50 to-white">
            <div className="max-w-4xl mx-auto">
                <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight text-gray-900 mb-6 transition-all duration-300">
                    {hook}
                </h1>
                <p className="text-xl md:text-2xl text-gray-600 mb-10 max-w-2xl mx-auto">
                    {subheading}
                </p>
                <div className="flex flex-col items-center">
                    <button
                        onClick={onStart}
                        className="px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white text-lg font-bold rounded-full shadow-lg hover:shadow-xl transition-all transform hover:-translate-y-1 active:translate-y-0"
                    >
                        {ctaText}
                    </button>
                    {microcopy && (
                        <p className="mt-4 text-sm text-gray-500 italic">
                            {microcopy}
                        </p>
                    )}
                </div>
            </div>
        </section>
    );
}
