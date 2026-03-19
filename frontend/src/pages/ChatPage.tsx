import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { Send, Upload, FileText, Bot, User, Loader2 } from 'lucide-react'
import { chatApi } from '../services/chatService'
import api from '../lib/api'
import type { ChatMessage } from '../types'

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Hello! I can help you manipulate extracted data using natural language. Upload a file or describe what you\'d like to do.',
      timestamp: new Date().toISOString(),
    },
  ])
  const [input, setInput] = useState('')
  const [uploadedFile, setUploadedFile] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const chatMutation = useMutation({
    mutationFn: async (query: string) => {
      return chatApi.send(query, 'default')
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.reply || data.result || data.message || JSON.stringify(data, null, 2),
          timestamp: new Date().toISOString(),
        },
      ])
    },
    onError: (err: any) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message || 'Something went wrong. Please try again.'}`,
          timestamp: new Date().toISOString(),
        },
      ])
    },
  })

  const handleSend = () => {
    if (!input.trim() || chatMutation.isPending) return
    const userMessage: ChatMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    chatMutation.mutate(input.trim())
    setInput('')
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    try {
      await api.post('/chat/upload-and-modify', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setUploadedFile(file.name)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `File "${file.name}" uploaded successfully. You can now ask me to modify it.`, timestamp: new Date().toISOString() },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Failed to upload "${file.name}". Please try again.`, timestamp: new Date().toISOString() },
      ])
    }
  }

  const samplePrompts = [
    'Add a "VAT Amount" column = Total * 0.15',
    'Remove the "Internal Notes" column',
    'Sort by Invoice Date descending',
    'Keep only rows where Status is PAID',
    'Convert all dates to DD/MM/YYYY format',
    'Rename "Cust Name" to "Customer Name"',
  ]

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text)]">Chat Engine</h1>
        <p className="text-sm text-[var(--color-text-muted)]">
          Manipulate data using natural language with hash-protected integrity
        </p>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* Chat Area */}
        <Card className="flex flex-1 flex-col overflow-hidden">
          {/* Messages */}
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
              >
                {msg.role === 'assistant' && (
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[var(--color-primary)]">
                    <Bot size={16} className="text-white" />
                  </div>
                )}
                <div
                  className={`max-w-[70%] rounded-xl px-4 py-3 text-sm ${
                    msg.role === 'user'
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'bg-[var(--color-surface-hover)] text-[var(--color-text)]'
                  }`}
                >
                  <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
                </div>
                {msg.role === 'user' && (
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[var(--color-secondary)]">
                    <User size={16} className="text-white" />
                  </div>
                )}
              </div>
            ))}
            {chatMutation.isPending && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-primary)]">
                  <Bot size={16} className="text-white" />
                </div>
                <div className="flex items-center gap-2 rounded-xl bg-[var(--color-surface-hover)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
                  <Loader2 size={14} className="animate-spin" /> Thinking...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-[var(--color-border)] p-4">
            {uploadedFile && (
              <div className="mb-2 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
                <FileText size={12} /> Working with: {uploadedFile}
              </div>
            )}
            <div className="flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileUpload}
                accept=".json,.jsonl,.csv,.xlsx,.txt"
              />
              <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                <Upload size={14} />
              </Button>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                placeholder="Describe what you want to do..."
                className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-primary)] focus:outline-none"
              />
              <Button onClick={handleSend} disabled={!input.trim() || chatMutation.isPending}>
                <Send size={14} />
              </Button>
            </div>
          </div>
        </Card>

        {/* Sample Prompts Sidebar */}
        <div className="w-72 flex-shrink-0">
          <Card title="Quick Actions" description="Click to use">
            <div className="space-y-2">
              {samplePrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => setInput(prompt)}
                  className="block w-full rounded-lg border border-[var(--color-border)] p-3 text-left text-xs text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-primary)] hover:text-[var(--color-text)]"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
