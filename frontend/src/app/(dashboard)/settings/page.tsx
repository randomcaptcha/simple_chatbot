'use client';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export default function SettingsPage() {
    const [name, setName] = useState('Jane Doe');

    return (
        <>
            <h2 className="mb-4 text-2xl font-semibold">Settings</h2>

            <label className="mb-2 block text-sm font-medium">Display name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} className="w-64" />

            <Button className="mt-4" onClick={() => alert('Saved 🚀')}>
                Save
            </Button>
        </>
    );
}