import '../globals.css';
import Sidebar from '@/components/ui/Sidebar';
import type { ReactNode } from 'react';

export const metadata = {
    title: 'GenAI SaaS',
    description: 'Starter template with sidebar',
};

export default function DashboardLayout({ children }: { children: ReactNode }) {
    return (
        <div className="flex h-screen">
            <Sidebar />
            <main className="flex-1 overflow-hidden">{children}</main>
        </div>
    );
}