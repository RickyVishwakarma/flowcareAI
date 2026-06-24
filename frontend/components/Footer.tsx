import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-teal-500 to-emerald-500 text-white">
                <svg width="15" height="15" viewBox="0 0 24 24">
                  <path d="M8 12 L14.5 7.5 M8 12 L14.5 16.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
                  <circle cx="6.5" cy="12" r="2.4" fill="currentColor" />
                  <circle cx="16" cy="7" r="2.4" fill="currentColor" />
                  <circle cx="16" cy="17" r="2.4" fill="currentColor" />
                </svg>
              </span>
              <span className="font-display text-base font-extrabold text-ink">FlowCare AI</span>
            </div>
            <p className="mt-3 max-w-sm text-sm text-slate-500">
              Automate the entire healthcare referral lifecycle — intake, extraction,
              verification, scheduling — with AI and a visual workflow engine.
            </p>
          </div>
          <FooterCol title="Product" links={[["/dashboard", "Dashboard"], ["/workflows", "Workflow builder"], ["/providers", "Provider matching"], ["/referrals", "Referrals"]]} />
          <FooterCol title="Account" links={[["/login", "Sign in"], ["/signup", "Get started"], ["/forgot-password", "Reset password"]]} />
        </div>
        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-slate-100 pt-6 text-xs text-slate-400 sm:flex-row">
          <p>© {new Date().getFullYear()} FlowCare AI. Portfolio reference project.</p>
          <p>Built with FastAPI · Next.js · Anthropic Claude</p>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h4>
      <ul className="mt-3 space-y-2">
        {links.map(([href, label]) => (
          <li key={href}>
            <Link href={href} className="text-sm text-slate-600 transition hover:text-brand">{label}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
