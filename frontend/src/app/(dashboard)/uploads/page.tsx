'use client';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

export default function UploadsPage() {
    const [files, setFiles] = useState<File[]>([]);

    const handleSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files) return;
        setFiles(Array.from(e.target.files));
        // TODO: upload to S3 / API
    };

    return (
        <>
            <h2 className="mb-4 text-2xl font-semibold">Upload Proposals</h2>
            <input type="file" multiple onChange={handleSelect} className="mb-4" />
            <ul className="list-disc pl-6">
                {files.map((f) => (
                    <li key={f.name}>{f.name}</li>
                ))}
            </ul>
            {!!files.length && (
                <Button className="mt-4" onClick={() => alert('Pretend upload 🚀')}>
                    Upload
                </Button>
            )}
        </>
    );
}