"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href;
  return (
    <Link
      href={href}
      className={`relative text-sm font-medium transition-colors py-1 ${
        active ? "text-zinc-900" : "text-zinc-500 hover:text-zinc-900"
      }`}
    >
      {children}
      <span
        className={`absolute -bottom-[17px] left-0 right-0 h-px transition-opacity ${
          active ? "bg-zinc-900 opacity-100" : "opacity-0"
        }`}
      />
    </Link>
  );
}

export default function Nav() {
  return (
    <nav className="border-b border-zinc-200/70 bg-white/80 backdrop-blur-md sticky top-0 z-20">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-[15px] tracking-tight flex items-baseline gap-1.5 text-zinc-900">
          <span className="font-semibold">APIForge</span>
          <span className="font-medium text-zinc-400">AI</span>
        </Link>
        <div className="flex items-center gap-8">
          <NavLink href="/">Upload</NavLink>
          <NavLink href="/dashboard">Dashboard</NavLink>
        </div>
      </div>
    </nav>
  );
}
