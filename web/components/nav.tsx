"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";

import { ThemeToggle } from "./theme-toggle";

type NavProps = {
  username: string;
};

const links = [
  { href: "/", label: "dashboard" },
  { href: "/sources", label: "sources" },
  { href: "/logs", label: "logs" },
  { href: "/rules", label: "rules" },
  { href: "/alerts", label: "alerts" },
];

export function Nav({ username }: NavProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function onLogout() {
    setLoading(true);
    try {
      await api("/auth/logout", { method: "POST" });
      router.replace("/login");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <header className="frame topbar">
      <Link className="brand brand-link" href="/">
        <div className="brand-mark" aria-hidden="true" />
        <div className="brand-copy">
          <span className="eyebrow">llmh</span>
          <span className="subtitle">archive, search, alert</span>
        </div>
      </Link>
      <nav className="nav">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`nav-link${pathname === link.href ? " active" : ""}`}
          >
            {link.label}
          </Link>
        ))}
      </nav>
      <div className="nav">
        <Link className={`nav-link${pathname === "/profile" ? " active" : ""}`} href="/profile">
          {username}
        </Link>
        <ThemeToggle />
        <button className="ghost-button mono" type="button" disabled={loading} onClick={onLogout}>
          {loading ? "signing out" : "sign out"}
        </button>
      </div>
    </header>
  );
}
