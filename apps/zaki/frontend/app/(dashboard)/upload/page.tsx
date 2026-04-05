'use client'
import { useState, useRef } from 'react'
import { Upload, FileSpreadsheet, CheckCircle, XCircle, Download } from 'lucide-react'
import { api } from '@/lib/api'

export default function UploadPage() {
  const [dragging, setDragging] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    if (!file.name.match(/\.(csv|xlsx|xls)$/i)) {
      setError('Only CSV and Excel files supported')
      return
    }
    setUploading(true)
    setError('')
    setResult(null)
    try {
      const res = await api.uploadCSV(file)
      setResult(res)
    } catch (err: any) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  async function downloadTemplate() {
    const t = await api.getUploadTemplate()
    const rows = [t.columns.join(','), Object.values(t.example_row).join(',')]
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'zaki_template.csv'
    a.click()
  }

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-white">Upload Financial Data</h1>
        <p className="text-zaki-muted text-sm mt-1">Import transactions from CSV or Excel files</p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all ${
          dragging ? 'border-purple-500 bg-purple-600/10' : 'border-zaki-border hover:border-purple-600/50 hover:bg-zaki-card'
        }`}>
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
          onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
        {uploading ? (
          <div className="space-y-2">
            <div className="w-12 h-12 mx-auto rounded-full border-2 border-purple-500 border-t-transparent animate-spin" />
            <p className="text-white font-medium">Processing file…</p>
          </div>
        ) : (
          <>
            <Upload size={40} className="mx-auto text-zaki-muted mb-3" />
            <p className="text-white font-medium">Drop your file here, or click to browse</p>
            <p className="text-zaki-muted text-sm mt-1">CSV, XLSX, XLS supported</p>
          </>
        )}
      </div>

      {/* Result */}
      {result && (
        <div className={`rounded-xl border p-5 ${result.status === 'done' ? 'border-green-500/30 bg-green-500/10' : 'border-red-500/30 bg-red-500/10'}`}>
          <div className="flex items-center gap-2 mb-3">
            {result.status === 'done'
              ? <CheckCircle size={20} className="text-green-400" />
              : <XCircle size={20} className="text-red-400" />}
            <span className="font-semibold text-white">{result.filename}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="bg-zaki-card/50 rounded-lg p-3">
              <div className="text-green-400 font-bold text-lg">{result.rows_imported}</div>
              <div className="text-zaki-muted">rows imported</div>
            </div>
            <div className="bg-zaki-card/50 rounded-lg p-3">
              <div className="text-red-400 font-bold text-lg">{result.rows_failed}</div>
              <div className="text-zaki-muted">rows failed</div>
            </div>
          </div>
          {result.rows_imported > 0 && (
            <a href="/transactions" className="mt-3 inline-block text-sm text-purple-400 hover:underline">
              View imported transactions →
            </a>
          )}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-400 text-sm">{error}</div>
      )}

      {/* Template */}
      <div className="bg-zaki-card border border-zaki-border rounded-xl p-5">
        <div className="flex items-center gap-3 mb-3">
          <FileSpreadsheet size={20} className="text-purple-400" />
          <h2 className="font-semibold text-white text-sm">CSV Format Guide</h2>
        </div>
        <div className="space-y-1 text-xs text-zaki-muted font-mono mb-4">
          <div className="text-purple-300">date, amount, type, category, description, reference, currency</div>
          <div>2026-01-15, 5000, income, Sales, Invoice payment, INV-001, USD</div>
          <div>2026-01-16, 1200, expense, Rent, Office rent, -, USD</div>
        </div>
        <button onClick={downloadTemplate}
          className="flex items-center gap-2 text-sm text-purple-400 hover:text-purple-300 border border-purple-600/30 hover:border-purple-500 px-3 py-1.5 rounded-lg transition-all">
          <Download size={14} /> Download template
        </button>
      </div>
    </div>
  )
}
