import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { NavAuth } from "@/components/NavAuth";
import { VerifyBanner } from "@/components/VerifyBanner";

export const metadata: Metadata = {
  title: "FlowCare AI",
  description: "Healthcare referral automation + workflow builder",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="sticky top-0 z-30 h-14 border-b border-slate-200 bg-white">
          <nav className="mx-auto flex h-full max-w-6xl items-center gap-6 px-6">
            <Link href="/" className="font-semibold text-brand-dark">
              FlowCare&nbsp;AI
            </Link>
            <Link href="/dashboard" className="text-sm text-slate-600 hover:text-brand">
              Dashboard
            </Link>
            <Link href="/referrals" className="text-sm text-slate-600 hover:text-brand">
              Referrals
            </Link>
            <Link href="/review" className="text-sm text-slate-600 hover:text-brand">
              Review Queue
            </Link>
            <Link href="/tasks" className="text-sm text-slate-600 hover:text-brand">
              Tasks
            </Link>
            <Link href="/workflows" className="text-sm text-slate-600 hover:text-brand">
              Workflow Builder
            </Link>
            <NavAuth />
          </nav>
        </header>
        <VerifyBanner />
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
