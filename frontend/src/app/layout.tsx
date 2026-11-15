import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'DiffGuard — AI-Powered Git Diff & PR Review Agent',
  description:
    'An agentic code review system analyzing git diffs, inspecting logic and security risks, and returning structured findings.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen bg-gray-950 text-gray-100">{children}</body>
    </html>
  );
}

