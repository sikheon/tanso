import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "E.L.O — Eco Logistics Optimizer",
  description: "LLM-driven multi-engine routing with CO₂ optimization",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
