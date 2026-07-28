import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Penguin — AI agent for your codebase",
  description: "Half debugging tool, half seance.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
