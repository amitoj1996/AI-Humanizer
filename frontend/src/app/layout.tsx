import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Humanizer & Detector",
  description:
    "Detect AI-generated text and humanize it — fully local, fully private.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased dark">
      <body className="min-h-full flex flex-col bg-zinc-950 text-zinc-100 font-sans">
        {children}
      </body>
    </html>
  );
}
