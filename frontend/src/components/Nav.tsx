"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href;
  return (
    <Link
      href={href}
      className={`text-sm font-medium transition-colors ${
        active ? "text-zinc-900" : "text-zinc-500 hover:text-zinc-900"
      }`}
    >
      {children}
    </Link>
  );
}

export default function Nav() {
  return (
    <nav className="border-b border-zinc-200 bg-white/80 backdrop-blur sticky top-0 z-20">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="font-extrabold text-lg tracking-tight flex items-center gap-2 text-zinc-900">
          <span className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center text-sm">⚡</span>
          APIForge AI
        </Link>
        <div className="flex items-center gap-6">
          <NavLink href="/">Upload</NavLink>
          <NavLink href="/dashboard">Dashboard</NavLink>
        </div>
      </div>
    </nav>
  );
}
