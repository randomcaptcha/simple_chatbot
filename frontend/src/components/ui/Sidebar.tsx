'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MessageCircle, Link2, Upload, Settings } from 'lucide-react';
import clsx from 'clsx';

const nav = [
    { href: '/chat', label: 'Chat', icon: MessageCircle },
    { href: '/connections', label: 'Connections', icon: Link2 },
    { href: '/uploads', label: 'Uploads', icon: Upload },
    { href: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
    const path = usePathname();
    return (
        <aside className="sticky top-0 h-screen w-64 bg-black rounded-r-2xl p-6 shadow-2xl flex-shrink-0">
            <h1 className="mb-8 text-2xl font-bold text-white">GenAI SaaS</h1>
            <nav className="flex flex-col gap-3">
                {nav.map(({ href, label, icon: Icon }) => (
                    <Link
                        key={href}
                        href={href}
                        className={clsx(
                            'flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200',
                            path === href
                                ? 'bg-white/10 text-white shadow-lg backdrop-blur-sm'
                                : 'text-gray-300 hover:bg-white/5 hover:text-white'
                        )}
                    >
                        <Icon size={18} />
                        {label}
                    </Link>
                ))}
            </nav>
        </aside>
    );
}