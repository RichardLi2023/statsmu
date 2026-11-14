import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mauritius in numbers",
  description: "Statistics Mauritius data, made easy to read. Source: Statistics Mauritius.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif" }}>{children}</body>
    </html>
  );
}
