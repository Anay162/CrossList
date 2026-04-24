import type { Metadata } from "next";
import "./globals.css";

const faviconSvg = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#2563EB"/>
  <text x="32" y="42" text-anchor="middle" font-size="34" font-family="Arial, Helvetica, sans-serif" font-weight="700" fill="white">C</text>
</svg>
`;

export const metadata: Metadata = {
  title: "CrossList — Find the transfer credits other tools miss",
  description: "Find the transfer credits other tools miss.",
  icons: {
    icon: `data:image/svg+xml,${encodeURIComponent(faviconSvg)}`,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
