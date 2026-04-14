import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: f.write(content)
    print(f"Created: {path}")

def setup_frontend():
    fe_dir = os.path.join(os.getcwd(), 'frontend')
    
    # 1. API Client
    api_content = """const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
export interface FunnelData { id: number; name: string; slug: string; landing_page: any; questions: any[]; }
export async function fetchFunnel(slug: string): Promise<FunnelData> {
  const res = await fetch(`${API_BASE_URL}/funnels/${slug}/`);
  return res.json();
}
export async function createLead(funnelId: number, data: any) {
  const res = await fetch(`${API_BASE_URL}/leads/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ funnel: funnelId, ...data }),
  });
  return res.json();
}
export async function submitAssessment(leadId: string, answers: any[]) {
  const res = await fetch(`${API_BASE_URL}/leads/${leadId}/submit-assessment/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });
  return res.json();
}
"""
    write_file(os.path.join(fe_dir, 'lib/api.ts'), api_content)

    # 2. Components (Simplified Hero for brevity in script, can be full)
    hero_content = """export default function Hero({ hook, subheading, ctaText, onStart }: any) {
  return (
    <section className="py-20 text-center bg-blue-50">
      <h1 className="text-5xl font-bold mb-6">{hook}</h1>
      <p className="text-xl mb-10">{subheading}</p>
      <button onClick={onStart} className="px-8 py-4 bg-blue-600 text-white rounded-full font-bold">{ctaText}</button>
    </section>
  );
}"""
    write_file(os.path.join(fe_dir, 'components/Hero.tsx'), hero_content)

    # 3. Assessment Form (Simplified logic)
    form_content = """import { useState } from 'react';
import { createLead, submitAssessment } from '../lib/api';
export default function AssessmentForm({ funnelId, questions, onComplete }: any) {
  const [step, setStep] = useState('LEAD');
  const [leadId, setLeadId] = useState('');
  const [curr, setCurr] = useState(0);
  const [ans, setAns] = useState<any[]>([]);
  if (step === 'LEAD') return (
    <form onSubmit={async (e:any) => { e.preventDefault(); const r = await createLead(funnelId, {first_name: e.target.name.value, email: e.target.email.value}); setLeadId(r.id); setStep('QA'); }}>
      <input name="name" placeholder="Name" required className="border p-2 mr-2" />
      <input name="email" placeholder="Email" required className="border p-2" />
      <button type="submit" className="bg-blue-600 text-white p-2 ml-2">Next</button>
    </form>
  );
  const q = questions[curr];
  return (
    <div>
      <h3>{q.text}</h3>
      {q.choices.length > 0 ? q.choices.map((c:any) => (
        <button key={c.id} onClick={() => { setAns([...ans, {question: q.id, choice: c.id}]); if(curr < questions.length-1) setCurr(curr+1); else submitAssessment(leadId, [...ans, {question: q.id, choice: c.id}]).then(onComplete); }} className="block border p-2 mb-2 w-full">{c.text}</button>
      )) : <textarea onBlur={(e) => { setAns([...ans, {question: q.id, text_value: e.target.value}]); if(curr < questions.length-1) setCurr(curr+1); else submitAssessment(leadId, [...ans, {question: q.id, text_value: e.target.value}]).then(onComplete); }} className="border p-2 w-full" />}
    </div>
  );
}"""
    write_file(os.path.join(fe_dir, 'components/AssessmentForm.tsx'), form_content)

    # 4. Results View
    results_content = """export default function ResultsView({ results }: any) {
  return (
    <div className="p-10 text-center">
      <h2 className="text-4xl font-bold mb-4">Your Score: {Math.round(results.score)}</h2>
      <p className="text-xl mb-8">{results.tier?.headline}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {results.insights.map((i:any, idx:number) => <div key={idx} className="border p-4"><h4>{i.title}</h4><p>{i.content}</p></div>)}
      </div>
    </div>
  );
}"""
    write_file(os.path.join(fe_dir, 'components/ResultsView.tsx'), results_content)

    # 5. Dynamic Page
    page_content = """'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { fetchFunnel } from '../../../lib/api';
import Hero from '../../../components/Hero';
import AssessmentForm from '../../../components/AssessmentForm';
import ResultsView from '../../../components/ResultsView';

export default function FunnelPage() {
  const { slug } = useParams();
  const [funnel, setFunnel] = useState<any>(null);
  const [view, setView] = useState('LANDING');
  const [res, setRes] = useState<any>(null);

  useEffect(() => { if(slug) fetchFunnel(slug as string).then(setFunnel); }, [slug]);
  if (!funnel) return <div>Loading...</div>;

  return (
    <main>
      {view === 'LANDING' && <Hero hook={funnel.landing_page.hero_hook_frustration} subheading={funnel.landing_page.hero_subheading} ctaText={funnel.landing_page.cta_text} onStart={() => setView('QA')} />}
      {view === 'QA' && <AssessmentForm funnelId={funnel.id} questions={funnel.questions} onComplete={(d:any) => { setRes(d); setView('RES'); }} />}
      {view === 'RES' && <ResultsView results={res} />}
    </main>
  );
}"""
    write_file(os.path.join(fe_dir, 'app/funnel/[slug]/page.tsx'), page_content)

if __name__ == "__main__":
    setup_frontend()
