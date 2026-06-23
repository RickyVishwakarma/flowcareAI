import Link from "next/link";

const features = [
  ["Referral intake", "PDF, image, fax, and web-form ingestion with secure storage."],
  ["OCR + AI extraction", "Tesseract + Claude turn documents into structured data with confidence scores."],
  ["Validation engine", "Required fields, dates, insurance completeness, duplicate detection."],
  ["Workflow builder", "Zapier-style triggers, conditions, and actions with retries and a DLQ."],
  ["Insurance & scheduling", "Mock payer eligibility and automatic appointment booking."],
  ["Audit & observability", "Immutable audit trail + Prometheus/Grafana dashboards."],
];

export default function Home() {
  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <p className="text-sm font-medium uppercase tracking-wide text-brand">
          Referral automation platform
        </p>
        <h1 className="text-4xl font-bold tracking-tight">
          Turn any referral into a scheduled patient — automatically.
        </h1>
        <p className="max-w-2xl text-slate-600">
          FlowCare AI ingests referrals from every channel, extracts and validates the data
          with AI, verifies insurance, and orchestrates the whole lifecycle through a visual
          workflow engine.
        </p>
        <div className="flex gap-3 pt-2">
          <Link
            href="/referrals"
            className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark"
          >
            Upload a referral
          </Link>
          <Link
            href="/workflows"
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium hover:border-brand"
          >
            Open workflow builder
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map(([title, body]) => (
          <div key={title} className="rounded-lg border border-slate-200 bg-white p-5">
            <h3 className="font-semibold text-slate-900">{title}</h3>
            <p className="mt-1 text-sm text-slate-600">{body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
