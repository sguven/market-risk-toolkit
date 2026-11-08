import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/risklab/AppShell";
import { api, safe } from "@/lib/api";

export const metadata: Metadata = {
  title: "RiskLab — Market Risk, FRTB & Basel",
  description: "Understand Risk. Explore the Models. Calculate the Capital.",
};


export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const health = await safe(api.health());
  return (
    <html lang="en">
      <body>
        <AppShell health={health.data} healthError={health.error}>
          {children}
        </AppShell>
      </body>
    </html>
  );
}
