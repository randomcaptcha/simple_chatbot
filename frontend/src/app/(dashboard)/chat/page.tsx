'use client';
import { useRef, useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, User, Bot } from 'lucide-react';

type Msg = { role: 'user' | 'assistant'; content: string };

// MCP server URL - in production this would come from environment variables
const MCP_SERVER = process.env.NEXT_PUBLIC_MCP_SERVER_URL || 'http://127.0.0.1:5000';

export default function ChatPage() {
    const [msgs, setMsgs] = useState<Msg[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const send = async () => {
        if (!input.trim() || isLoading) return;

        const userMsg: Msg = { role: 'user', content: input };
        setMsgs((m) => [...m, userMsg]);
        setInput('');
        setIsLoading(true);

        let botMsg: Msg = { role: 'assistant', content: '' };
        try {
            // All queries go through /ask endpoint
            const res = await fetch(`${MCP_SERVER}/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: input })
            });
            const data = await res.json();
            if (res.ok && data.answer) {
                botMsg.content = data.answer;
            } else {
                botMsg.content = data.error || 'An error occurred.';
            }
        } catch (err) {
            botMsg.content = 'Error connecting to backend.';
        }
        setMsgs((m) => [...m, botMsg]);
        setIsLoading(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    };

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [msgs]);

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [input]);

    return (
        <div className="flex flex-col h-screen">
            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-6">
                {msgs.length === 0 ? (
                    <div className="flex items-center justify-center h-full">
                        <div className="text-center text-gray-500">
                            <Bot className="mx-auto h-12 w-12 mb-4 text-gray-400" />
                            <h3 className="text-lg font-medium">How can I help you today?</h3>
                        </div>
                    </div>
                ) : (
                    <div className="max-w-4xl mx-auto">
                        {msgs.map((msg, i) => (
                            <div
                                key={i}
                                className={`py-6 ${msg.role === 'user' ? 'bg-gray-50' : 'bg-white'
                                    }`}
                            >
                                <div className="max-w-3xl mx-auto flex gap-4 px-4">
                                    <div className="flex-shrink-0">
                                        {msg.role === 'user' ? (
                                            <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
                                                <User className="w-5 h-5 text-white" />
                                            </div>
                                        ) : (
                                            <div className="w-8 h-8 rounded-full bg-green-600 flex items-center justify-center">
                                                <Bot className="w-5 h-5 text-white" />
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="prose prose-sm max-w-none">
                                            <p className="text-gray-900 leading-relaxed whitespace-pre-wrap">
                                                {msg.content}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                        {isLoading && (
                            <div className="py-6 bg-white">
                                <div className="max-w-3xl mx-auto flex gap-4 px-4">
                                    <div className="flex-shrink-0">
                                        <div className="w-8 h-8 rounded-full bg-green-600 flex items-center justify-center">
                                            <Bot className="w-5 h-5 text-white" />
                                        </div>
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex space-x-1">
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>
                )}
            </div>

            {/* Input Area - Sticky at bottom */}
            <div className="sticky bottom-0 border-t bg-white">
                <div className="max-w-4xl mx-auto p-4">
                    <div className="relative">
                        <Textarea
                            ref={textareaRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Message ChatGPT..."
                            className="w-full resize-none border border-gray-300 rounded-lg shadow-sm focus-visible:ring-2 focus-visible:ring-green-500 focus-visible:ring-offset-0 focus-visible:border-green-500 pr-12 py-3 text-base"
                            rows={1}
                        />
                        <Button
                            onClick={send}
                            disabled={!input.trim() || isLoading}
                            className="absolute right-2 top-2 h-8 w-8 p-0 rounded-md bg-green-600 hover:bg-green-700 disabled:bg-gray-300"
                        >
                            <Send className="h-4 w-4" />
                        </Button>
                    </div>
                    <p className="text-xs text-gray-500 mt-2 text-center">
                        ChatGPT can make mistakes. Consider checking important information.
                    </p>
                </div>
            </div>
        </div>
    );
}