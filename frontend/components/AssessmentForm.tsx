import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Question, createLead, submitAssessment, ResultData } from '../lib/api';
import { ChevronRight, ChevronLeft, Send, CheckCircle2 } from 'lucide-react';

interface AssessmentFormProps {
    funnelId: number;
    questions: Question[];
    onComplete: (results: ResultData) => void;
}

export default function AssessmentForm({ funnelId, questions, onComplete }: AssessmentFormProps) {
    const [step, setStep] = useState<'LEAD' | 'QUESTIONS'>('LEAD');
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    const [leadId, setLeadId] = useState<string | null>(null);
    const [leadData, setLeadData] = useState({ first_name: '', email: '', phone: '' });
    const [answers, setAnswers] = useState<{ question: number; choice?: number; text_value?: string }[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleLeadSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            const res = await createLead(funnelId, leadData);
            setLeadId(res.id);
            setStep('QUESTIONS');
        } catch (err) {
            console.error(err);
            alert('Failed to start assessment. Please try again.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleAnswer = (questionId: number, choiceId?: number, textValue?: string) => {
        setAnswers(prev => {
            const filtered = prev.filter(a => a.question !== questionId);
            return [...filtered, { question: questionId, choice: choiceId, text_value: textValue }];
        });
    };

    const nextQuestion = () => {
        if (currentQuestionIndex < questions.length - 1) {
            setCurrentQuestionIndex(prev => prev + 1);
        } else {
            handleSubmit();
        }
    };

    const prevQuestion = () => {
        if (currentQuestionIndex > 0) {
            setCurrentQuestionIndex(prev => prev - 1);
        }
    };

    const handleSubmit = async () => {
        if (!leadId) return;
        setIsSubmitting(true);
        try {
            const res = await submitAssessment(leadId, answers);
            onComplete(res);
        } catch (err) {
            console.error(err);
            alert('Failed to submit results. Please try again.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const currentQuestion = questions[currentQuestionIndex];
    const progress = ((currentQuestionIndex + (step === 'LEAD' ? 0 : 1)) / (questions.length + 1)) * 100;

    if (step === 'LEAD') {
        return (
            <div className="max-w-xl mx-auto p-8 bg-white rounded-3xl shadow-xl border border-gray-100">
                <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">First, tell us a bit about yourself</h2>
                <form onSubmit={handleLeadSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">First Name</label>
                        <input
                            required
                            type="text"
                            value={leadData.first_name}
                            onChange={e => setLeadData({ ...leadData, first_name: e.target.value })}
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                            placeholder="John"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">Email Address</label>
                        <input
                            required
                            type="email"
                            value={leadData.email}
                            onChange={e => setLeadData({ ...leadData, email: e.target.value })}
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                            placeholder="john@example.com"
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="w-full py-4 bg-blue-600 text-white rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-blue-700 transition-all disabled:opacity-50"
                    >
                        {isSubmitting ? 'Starting...' : 'Go to Questions'} <ChevronRight size={20} />
                    </button>
                </form>
            </div>
        );
    }

    return (
        <div className="max-w-2xl mx-auto">
            <div className="mb-8">
                <div className="flex justify-between items-end mb-2">
                    <span className="text-sm font-bold text-blue-600">Question {currentQuestionIndex + 1} of {questions.length}</span>
                    <span className="text-sm font-medium text-gray-400">{Math.round(progress)}% Complete</span>
                </div>
                <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                    <motion.div
                        className="h-full bg-blue-600"
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            <AnimatePresence mode="wait">
                <motion.div
                    key={currentQuestion.id}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="bg-white p-8 md:p-12 rounded-3xl shadow-xl border border-gray-100"
                >
                    <h3 className="text-2xl font-bold text-gray-900 mb-8">{currentQuestion.text}</h3>

                    <div className="space-y-4">
                        {currentQuestion.choices.length > 0 ? (
                            currentQuestion.choices.map(choice => {
                                const isActive = answers.find(a => a.question === currentQuestion.id)?.choice === choice.id;
                                return (
                                    <button
                                        key={choice.id}
                                        onClick={() => handleAnswer(currentQuestion.id, choice.id)}
                                        className={`w-full text-left p-5 rounded-2xl border-2 transition-all flex items-center justify-between ${isActive ? 'border-blue-600 bg-blue-50' : 'border-gray-100 hover:border-gray-300'
                                            }`}
                                    >
                                        <span className={`font-semibold ${isActive ? 'text-blue-700' : 'text-gray-700'}`}>{choice.text}</span>
                                        {isActive && <CheckCircle2 className="text-blue-600" size={24} />}
                                    </button>
                                );
                            })
                        ) : (
                            <textarea
                                className="w-full p-5 rounded-2xl border-2 border-gray-100 focus:border-blue-600 focus:ring-0 transition-all min-h-[150px] outline-none"
                                placeholder="Type your answer here..."
                                value={answers.find(a => a.question === currentQuestion.id)?.text_value || ''}
                                onChange={(e) => handleAnswer(currentQuestion.id, undefined, e.target.value)}
                            />
                        )}
                    </div>

                    <div className="flex justify-between mt-12">
                        <button
                            onClick={prevQuestion}
                            className="flex items-center gap-2 text-gray-500 font-bold hover:text-gray-900 transition-colors"
                        >
                            <ChevronLeft size={20} /> Previous
                        </button>
                        <button
                            onClick={nextQuestion}
                            disabled={currentQuestion.choices.length > 0 && !answers.find(a => a.question === currentQuestion.id)}
                            className="px-8 py-3 bg-blue-600 text-white rounded-full font-bold flex items-center gap-2 hover:bg-blue-700 transition-all disabled:opacity-50 disabled:grayscale"
                        >
                            {currentQuestionIndex === questions.length - 1 ? (isSubmitting ? 'Submitting...' : 'See My Results') : 'Next'}
                            {currentQuestionIndex === questions.length - 1 ? <Send size={20} /> : <ChevronRight size={20} />}
                        </button>
                    </div>
                </motion.div>
            </AnimatePresence>
        </div>
    );
}
