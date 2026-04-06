import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { LayoutShell } from "./LayoutShell";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "AI Stock Scanner – Indian Market",
  description: "AI-powered stock market scanning and prediction platform for the Indian stock market",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`min-h-screen bg-background text-slate-100 antialiased ${inter.className}`}>
        <LayoutShell>{children}</LayoutShell>
      </body>
    </html>
  );
}
