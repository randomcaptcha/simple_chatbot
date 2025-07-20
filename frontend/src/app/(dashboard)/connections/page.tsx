import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const mock = [
    { name: 'PostgreSQL prod', url: 'https://mcp.example.com/psql', status: '✅' },
    { name: 'Salesforce', url: 'https://mcp.example.com/sf', status: '✅' },
    { name: 'Github Issues', url: 'https://mcp.example.com/gh', status: '⚠️' },
];

export default function ConnectionsPage() {
    return (
        <>
            <h2 className="mb-4 text-2xl font-semibold">MCP Connections</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
                {mock.map((c) => (
                    <Card key={c.url}>
                        <CardHeader>
                            <CardTitle className="flex items-center justify-between">
                                {c.name} <span>{c.status}</span>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="truncate text-sm text-slate-500">{c.url}</p>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </>
    );
}