"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Three destinations, thumb-height, pinned above the home indicator. A bottom
 * bar rather than a top nav because this is used one-handed on a phone.
 */
const ITEMS = [
  { href: "/", label: "Today" },
  { href: "/research", label: "Research" },
  { href: "/settings", label: "Alerts" },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-ink/95 backdrop-blur"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <ul className="mx-auto flex w-full max-w-[560px]">
        {ITEMS.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex h-[3.25rem] items-center justify-center text-[0.8125rem] transition-colors ${
                  active ? "text-text" : "text-faint"
                }`}
              >
                <span className="relative">
                  {item.label}
                  {active && (
                    <span className="absolute -bottom-2 left-1/2 h-px w-5 -translate-x-1/2 bg-signal" />
                  )}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
