import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Voice Agent Platform",
  description: "Enterprise AI voice agents — real-time calls, CRM, analytics.",
};

const navLinks = [
  { href: "/", label: "Dashboard" },
  { href: "/calls", label: "Calls" },
  { href: "/call", label: "Live Call" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-gray-950 text-gray-100 min-h-screen`}>
        {/* Sidebar */}
        <div className="flex min-h-screen">
          <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col fixed h-full z-20">
            <div className="p-5 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🎙️</span>
                <span className="font-bold text-white text-sm leading-tight">
                  AI Voice<br />Platform
                </span>
              </div>
            </div>
            <nav className="flex-1 p-4 space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="flex items-center px-3 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors text-sm font-medium"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
              v1.0.0
            </div>
          </aside>

          {/* Main content */}
          <main className="ml-56 flex-1 p-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
