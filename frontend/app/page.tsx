import Link from "next/link";
import { Footer } from "@/components/Footer";

const FEATURES: { title: string; body: string; icon: React.ReactNode }[] = [
  {
    title: "Omni-channel intake",
    body: "PDFs, scanned images, faxes, and web forms — captured, stored securely, and given a unique referral ID.",
    icon: <path d="M4 4h16v12H4z M8 20h8 M12 16v4" />,
  },
  {
    title: "AI extraction",
    body: "Claude turns messy documents into structured patient data with per-field confidence scores.",
    icon: <path d="M12 2v4 M12 18v4 M4.9 4.9l2.8 2.8 M16.3 16.3l2.8 2.8 M2 12h4 M18 12h4 M4.9 19.1l2.8-2.8 M16.3 7.7l2.8-2.8" />,
  },
  {
    title: "Validation engine",
    body: "Required fields, date formats, insurance completeness, and duplicate detection — automatically.",
    icon: <path d="M9 12l2 2 4-4 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />,
  },
  {
    title: "Visual workflow builder",
    body: "Drag-and-drop triggers, conditions, and actions. Retries, backoff, and a dead-letter queue built in.",
    icon: <path d="M6 4h6v6H6z M14 14h6v6h-6z M9 10v4h7" />,
  },
  {
    title: "Provider matching",
    body: "Rank in-network providers by specialty, insurance, and availability — and flag referral leakage.",
    icon: <path d="M3 12h4l2 5 4-12 2 7h6" />,
  },
  {
    title: "Audit & analytics",
    body: "An immutable trail of every action, plus a live operations dashboard and Prometheus metrics.",
    icon: <path d="M4 20V10 M10 20V4 M16 20v-8 M22 20H2" />,
  },
];

const STEPS = ["Intake", "OCR", "AI extract", "Validate", "Workflow", "Schedule"];

export default function Home() {
  return (
    <div className="space-y-24 pb-8">
      {/* Hero */}
      <section className="relative pt-8">
        <div className="pointer-events-none absolute inset-x-[-20%] -top-32 -z-10 h-[520px] bg-hero-glow" aria-hidden />
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div className="animate-fade-up">
            <span className="eyebrow">⚡ AI-native referral automation</span>
            <h1 className="mt-5 text-4xl font-extrabold leading-[1.1] sm:text-5xl lg:text-6xl">
              Turn every referral into a <span className="gradient-text">scheduled patient</span> — automatically.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-slate-400">
              FlowCare AI ingests referrals from any channel, extracts and validates the data
              with AI, verifies insurance, and orchestrates the whole lifecycle through a visual
              workflow engine — with a full audit trail.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className="btn-primary px-6 py-3 text-base">Get started free</Link>
              <Link href="#how" className="btn-ghost px-6 py-3 text-base">See how it works</Link>
            </div>
            <p className="mt-4 text-sm text-slate-500">No credit card · seeded demo · admin@flowcare.ai / admin12345</p>
          </div>
          <div className="animate-fade-up lg:justify-self-end">
            <HeroPreview />
          </div>
        </div>
      </section>

      {/* Trust strip */}
      <section className="text-center">
        <p className="text-sm font-medium uppercase tracking-wide text-slate-500">
          Built for clinics, specialty groups &amp; health systems
        </p>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
          {["Cardiology", "Neurology", "Orthopedics", "Endocrinology", "Pulmonology"].map((s) => (
            <span key={s} className="text-lg font-semibold text-slate-600">{s}</span>
          ))}
        </div>
      </section>

      {/* Stats band */}
      <section className="full-bleed border-y border-white/10 bg-surface py-14">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-6 lg:grid-cols-4">
          {[
            ["6+", "intake channels"],
            ["< 60s", "to structured data"],
            ["100%", "actions audited"],
            ["1M/mo", "referrals by design"],
          ].map(([n, l]) => (
            <div key={l} className="text-center">
              <div className="font-display text-4xl font-extrabold text-white">{n}</div>
              <div className="mt-1 text-sm text-slate-500">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-20">
        <div className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">Platform</span>
          <h2 className="mt-4 text-3xl font-extrabold sm:text-4xl">Everything a referral needs, in one place</h2>
          <p className="mt-3 text-slate-400">From the moment a fax lands to the moment the patient is booked.</p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="card p-6 transition hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-glow">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand/10 text-brand">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{f.icon}</svg>
              </span>
              <h3 className="mt-4 text-lg font-bold">{f.title}</h3>
              <p className="mt-2 text-sm text-slate-400">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20">
        <div className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">Pipeline</span>
          <h2 className="mt-4 text-3xl font-extrabold sm:text-4xl">From document to appointment</h2>
          <p className="mt-3 text-slate-400">A queue-based pipeline so the request path never blocks on a slow AI call.</p>
        </div>
        <div className="mt-12 flex flex-wrap items-center justify-center gap-3">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-3">
              <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-surface px-5 py-3">
                <span className="grid h-7 w-7 place-items-center rounded-full bg-brand text-xs font-bold text-[#08090c]">{i + 1}</span>
                <span className="font-semibold text-white">{s}</span>
              </div>
              {i < STEPS.length - 1 && <span className="text-slate-600">→</span>}
            </div>
          ))}
        </div>
      </section>

      {/* Workflow builder showcase */}
      <section id="workflow" className="scroll-mt-20 grid items-center gap-12 lg:grid-cols-2">
        <div>
          <span className="eyebrow">Most important module</span>
          <h2 className="mt-4 text-3xl font-extrabold sm:text-4xl">A workflow engine you can see</h2>
          <p className="mt-4 text-slate-400">
            Build automations like Zapier — but for referrals. Drag triggers, conditions, and
            actions onto a canvas, wire them together, and FlowCare runs them on every incoming
            referral with retries, backoff, and a dead-letter queue.
          </p>
          <ul className="mt-6 space-y-3 text-sm">
            {["IF insurance verified → schedule appointment", "IF missing insurance → request documents", "IF referral incomplete → create review task"].map((r) => (
              <li key={r} className="flex items-center gap-3">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-brand/10 text-brand">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l4 4 10-10" /></svg>
                </span>
                <code className="text-slate-300">{r}</code>
              </li>
            ))}
          </ul>
          <Link href="/workflows" className="btn-primary mt-8 px-6 py-3">Open the builder</Link>
        </div>
        <WorkflowPreview />
      </section>

      {/* CTA band */}
      <section className="full-bleed border-y border-white/10 py-16">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <div className="rounded-3xl border border-brand/20 bg-gradient-to-br from-brand/10 to-transparent p-10 shadow-glow">
            <h2 className="text-3xl font-extrabold sm:text-4xl">Ready to automate your referrals?</h2>
            <p className="mt-3 text-slate-400">Spin up the demo in minutes and watch a referral go from fax to scheduled patient.</p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/signup" className="btn-primary px-6 py-3 text-base">Get started free</Link>
              <Link href="/dashboard" className="btn-ghost px-6 py-3 text-base">View dashboard</Link>
            </div>
          </div>
        </div>
      </section>

      <div className="full-bleed">
        <Footer />
      </div>
    </div>
  );
}

function HeroPreview() {
  return (
    <div className="w-full max-w-md rounded-2xl border border-white/10 bg-surface p-5 shadow-card">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-slate-500">REF-1A2B3C4D</span>
        <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-xs font-medium text-emerald-300">validated</span>
      </div>
      <div className="mt-4 space-y-2 text-sm">
        {[
          ["Patient", "Jane Doe", "98%"],
          ["Insurance", "Blue Shield", "95%"],
          ["Diagnosis", "Hypertension", "91%"],
          ["Specialty", "Cardiology", "—"],
        ].map(([k, v, c]) => (
          <div key={k} className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2">
            <span className="text-slate-500">{k}</span>
            <span className="flex items-center gap-2">
              <span className="font-medium text-white">{v}</span>
              <span className="text-xs text-brand">{c}</span>
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-2 rounded-lg border border-brand/20 bg-brand/10 px-3 py-2 text-xs text-brand">
        <span className="grid h-5 w-5 place-items-center rounded-full bg-brand text-[#08090c]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l4 4 10-10" /></svg>
        </span>
        In-network provider matched · scheduling appointment…
      </div>
    </div>
  );
}

function WorkflowPreview() {
  const node = (label: string, color: string, cls: string) => (
    <div className={`absolute ${cls} rounded-lg border ${color} px-3 py-2 text-xs font-semibold`}>{label}</div>
  );
  return (
    <div className="relative h-72 overflow-hidden rounded-2xl border border-white/10 bg-surface p-4 shadow-card"
         style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
      <svg className="absolute inset-0 h-full w-full" aria-hidden>
        <path d="M120 56 C 180 56, 180 130, 240 130" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
        <path d="M120 56 C 180 56, 180 210, 240 210" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
      </svg>
      {node("referral.received", "border-violet-400/30 bg-violet-400/10 text-violet-200", "left-4 top-10")}
      {node("if · insurance", "border-amber-400/30 bg-amber-400/10 text-amber-200", "left-[150px] top-[40px]")}
      {node("verify_insurance", "border-sky-400/30 bg-sky-400/10 text-sky-200", "left-[240px] top-[116px]")}
      {node("create_task", "border-sky-400/30 bg-sky-400/10 text-sky-200", "left-[240px] top-[196px]")}
    </div>
  );
}
