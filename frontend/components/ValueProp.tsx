interface ValuePropProps {
    areas: string[];
}

export default function ValueProp({ areas }: ValuePropProps) {
    return (
        <section className="py-16 px-4 bg-white">
            <div className="max-w-6xl mx-auto">
                <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
                    Take this assessment so we can measure and improve three key areas:
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {areas.map((area, index) => (
                        <div key={index} className="p-8 bg-gray-50 rounded-2xl text-center border border-gray-100 hover:shadow-md transition-shadow">
                            <div className="w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center mx-auto mb-6 text-xl font-bold">
                                {index + 1}
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 leading-tight">
                                {area}
                            </h3>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
