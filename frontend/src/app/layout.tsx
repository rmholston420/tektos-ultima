import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tektos-Ultima v1",
  description: "Self-improving local coding agent with browser GUI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
