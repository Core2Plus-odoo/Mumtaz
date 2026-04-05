'use client'
import { useState, useRef } from 'react'
import { Mic, MicOff, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'

interface VoiceButtonProps {
  onTranscript: (text: string) => void
}

export default function VoiceButton({ onTranscript }: VoiceButtonProps) {
  const [state, setState] = useState<'idle' | 'recording' | 'processing'>('idle')
  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  async function toggle() {
    if (state === 'recording') {
      mediaRef.current?.stop()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      recorder.ondataavailable = e => chunksRef.current.push(e.data)
      recorder.onstop = async () => {
        setState('processing')
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        try {
          const res = await api.transcribeAudio(blob)
          if (res.text) onTranscript(res.text)
        } catch (err) {
          console.error('Transcription failed', err)
        } finally {
          setState('idle')
        }
      }
      recorder.start()
      mediaRef.current = recorder
      setState('recording')
    } catch {
      alert('Microphone access denied')
    }
  }

  const colors = {
    idle: 'bg-zaki-surface border-zaki-border text-zaki-muted hover:border-purple-500 hover:text-purple-400',
    recording: 'bg-red-500/20 border-red-500 text-red-400 animate-pulse-slow',
    processing: 'bg-purple-600/20 border-purple-600 text-purple-400',
  }

  return (
    <button onClick={toggle} title={state === 'recording' ? 'Stop recording' : 'Start voice input'}
      className={`p-2.5 rounded-lg border transition-all ${colors[state]}`}>
      {state === 'processing' ? <Loader2 size={18} className="animate-spin" />
       : state === 'recording' ? <MicOff size={18} />
       : <Mic size={18} />}
    </button>
  )
}
