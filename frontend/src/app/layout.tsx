import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Maritime Crew Orchestrator | AI-Powered Sign-On/Sign-Off",
  description: "Autonomous Maritime Crew Management powered by Claude Managed Agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-ocean antialiased">{children}</body>
    </html>
  );
}
