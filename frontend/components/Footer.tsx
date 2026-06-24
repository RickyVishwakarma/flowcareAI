import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-base">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-teal-400 to-emerald-400 text-[#08090c]">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12h4l2 5 4-12 2 7h6" /></svg>
              </span>
              <span className="font-display text-base font-extrabold text-white">FlowCare AI</span>
            </div>
            <p className="mt-3 max-w-sm text-sm text-slate-400">
              Automate the entire healthcare referral lifecycle — intake, extraction,
              verification, scheduling — with AI and a visual workflow engine.
            </p>
          </div>
          <FooterCol title="Product" links={[["/dashboard", "Dashboard"], ["/workflows", "Workflow builder"], ["/providers", "Provider matching"], ["/referrals", "Referrals"]]} />
          <FooterCol title="Account" links={[["/login", "Sign in"], ["/signup", "Get started"], ["/forgot-password", "Reset password"]]} />
        </div>
        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-white/10 pt-6 text-xs text-slate-500 sm:flex-row">
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
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
      <ul className="mt-3 space-y-2">
        {links.map(([href, label]) => (
          <li key={href}>
            <Link href={href} className="text-sm text-slate-400 transition hover:text-brand">{label}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
