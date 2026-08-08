import { useState, useEffect, useCallback, useRef } from 'react'
import MorphismTab from './MorphismTab.jsx'

// In production (single-service deploy), the API is served from the same origin,
// so use a relative base. In dev, fall back to the local backend.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.PROD ? '' : 'http://localhost:8000')
const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN ?? 'admin-token'
const VIEWER_TOKEN = import.meta.env.VITE_VIEWER_TOKEN ?? 'viewer-token'

// ── Utility ──────────────────────────────────────────────────────────
function auth(viewer = false) {
  return 'Bearer ' + (viewer ? VIEWER_TOKEN : ADMIN_TOKEN)
}

async function api(path, { method = 'GET', body, viewer = false } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: auth(viewer),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Request failed: ${res.status}`)
  }
  return res.json()
}

// ── Simple inlined bar-chart ─────────────────────────────────────────
function MiniBar({ data, labelKey, valueKey, color = '#6366f1', max }) {
  if (!data || data.length === 0) return <p className="text-sm text-slate-400">No data</p>
  const m = max ?? Math.max(...data.map(d => d[valueKey] ?? 0))
  return (
    <div className="space-y-1">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="w-20 truncate text-slate-500">{d[labelKey]}</span>
          <div className="flex-1 h-4 rounded bg-slate-100 overflow-hidden">
            <div className="h-full rounded transition-all" style={{ width: `${(d[valueKey] / (m || 1)) * 100}%`, backgroundColor: color }} />
          </div>
          <span className="w-16 text-right font-mono text-slate-700">{d[valueKey]}</span>
        </div>
      ))}
    </div>
  )
}

function Badge({ children, color = 'slate' }) {
  return <span className={`neu-pill neu-pill--${color || 'slate'}`}>{children}</span>
}

function LoadingSpinner() {
  return <div className="flex justify-center py-8"><div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-indigo-600" /></div>
}

// ── TAB COMPONENTS ───────────────────────────────────────────────────

// 1 ─── Overview Dashboard ──────────────────────────────────────────────
function OverviewTab() {
  const [scanData, setScanData] = useState([])
  const [report, setReport] = useState({ daily_earnings: [], weekly_earnings: [], payouts: [], pending_balance: 0, confirmed_balance: 0, notifications: [], compliance_health: {} })
  const [trackingCode, setTrackingCode] = useState('')
  const [purchaseAmount, setPurchaseAmount] = useState('')
  const [timeline, setTimeline] = useState([])
  const [status, setStatus] = useState('Ready')
  const [loading, setLoading] = useState(false)

  const loadReport = useCallback(async () => {
    try {
      const r = await api('/report', { viewer: true })
      setReport(r)
    } catch (e) { setStatus(e.message) }
  }, [])

  const loadTimeline = useCallback(async () => {
    try {
      const t = await api('/earnings/timeline?days=14', { viewer: true })
      setTimeline(t)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadReport(); loadTimeline() }, [loadReport, loadTimeline])

  const handleScan = async () => {
    setLoading(true); setStatus('Scanning...')
    try {
      const r = await api('/scan', { method: 'POST' })
      setScanData(r.products)
      if (!trackingCode && r.products.length) setTrackingCode(r.products[0].tracking_code)
      setStatus(`Scan complete - ${r.inserted} products`)
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const handlePurchase = async () => {
    setLoading(true); setStatus('Recording purchase...')
    try {
      await api('/purchase', { method: 'POST', body: { tracking_code: trackingCode, amount: purchaseAmount ? Number(purchaseAmount) : undefined } })
      setStatus('Purchase recorded')
      loadReport()
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const handleValidate = async () => {
    setLoading(true); setStatus('Validating...')
    try {
      const r = await api('/validate', { method: 'POST' })
      setStatus(`Validated ${r.confirmed} commissions`)
      loadReport()
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const handlePayout = async (method) => {
    setLoading(true); setStatus(`Payout via ${method}...`)
    try {
      const r = await api('/payout', { method: 'POST', body: { method } })
      setStatus(`Payout processed: $${r.amount} (${r.transaction_ref})`)
      loadReport()
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const ch = report.compliance_health || {}

  return (
    <div className="space-y-6">
      {/* Status bar */}
      <div className="flex items-center gap-3">
        <p className={`flex-1 rounded-lg p-3 text-sm shadow-sm ${loading ? 'bg-blue-50 text-blue-700' : 'bg-white text-slate-600'}`}>
          {loading && <span className="mr-2 inline-block h-3 w-3 animate-pulse rounded-full bg-blue-500" />}
          {status}
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card title="Pending Balance" value={`$${report.pending_balance.toFixed(2)}`} color="amber" />
        <Card title="Confirmed Balance" value={`$${report.confirmed_balance.toFixed(2)}`} color="green" />
        <Card title="Products Scanned" value={String(scanData.length)} color="blue" />
        <Card title="Payouts" value={String(report.payouts.length)} color="purple" />
      </div>

      {/* Operations */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Operations</h2>
        <div className="flex flex-wrap gap-2">
          <Btn onClick={handleScan} disabled={loading} color="slate">Scan Markets</Btn>
          <Btn onClick={handleValidate} disabled={loading} color="indigo">Validate Commissions</Btn>
          <Btn onClick={() => handlePayout('paypal')} disabled={loading} color="emerald">Payout PayPal</Btn>
          <Btn onClick={() => handlePayout('mpesa')} disabled={loading} color="teal">Payout M-Pesa</Btn>
          <Btn onClick={() => { loadReport(); loadTimeline() }} disabled={loading} color="sky">Refresh</Btn>
        </div>
        <div className="mt-4 flex flex-wrap gap-3">
          <input className="flex-1 min-w-[200px] rounded-lg border p-2 text-sm" placeholder="Tracking code" value={trackingCode} onChange={e => setTrackingCode(e.target.value)} />
          <input className="w-40 rounded-lg border p-2 text-sm" type="number" min="0" step="0.01" placeholder="Amount (optional)" value={purchaseAmount} onChange={e => setPurchaseAmount(e.target.value)} />
          <Btn onClick={handlePurchase} disabled={loading || !trackingCode} color="orange">Record Purchase</Btn>
        </div>
      </div>

      {/* Earnings Timeline */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Earnings Timeline (14 days)</h2>
        <MiniBar data={timeline} labelKey="date" valueKey="earnings" color="#059669" />
      </div>

      {/* Two columns: scanned products + payouts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">Scanned Products</h2>
          {scanData.length === 0 ? <p className="text-sm text-slate-400">Run a scan to see products.</p> : (
            <div className="max-h-64 overflow-y-auto space-y-2">
              {scanData.map((p, i) => (
                <div key={i} className="border-b pb-2 text-sm last:border-0">
                  <div className="flex justify-between">
                    <span className="font-medium">{p.name}</span>
                    <Badge color="blue">{p.network}</Badge>
                  </div>
                  <div className="text-slate-500">${p.price} · {(p.commission_rate * 100).toFixed(1)}% · <code className="text-xs">{p.tracking_code}</code></div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">Payout History</h2>
          {report.payouts.length === 0 ? <p className="text-sm text-slate-400">No payouts yet.</p> : (
            <div className="max-h-64 overflow-y-auto space-y-2">
              {report.payouts.map((p, i) => (
                <div key={i} className="border-b pb-2 text-sm last:border-0">
                  <div className="flex justify-between">
                    <span className="font-medium">{p.method.toUpperCase()}</span>
                    <Badge color={p.status === 'processed' ? 'green' : 'yellow'}>{p.status}</Badge>
                  </div>
                  <div className="text-slate-500">${p.amount.toFixed(2)} · <code className="text-xs">{p.transaction_ref}</code></div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Compliance Health */}
      {ch.health_score !== undefined && (
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">Compliance Health</h2>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-3xl font-bold" style={{ color: ch.health_score >= 90 ? '#059669' : ch.health_score >= 70 ? '#d97706' : '#dc2626' }}>{ch.health_score}%</span>
              <Badge color={ch.status === 'healthy' ? 'green' : ch.status === 'warning' ? 'yellow' : 'red'}>{ch.status}</Badge>
            </div>
            <div className="text-sm text-slate-500">
              {ch.total_compliance_checks} checks · {ch.failed_checks} failed · {ch.active_rules}/{ch.total_rules} rules active
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// 2 ─── Compliance Dashboard ──────────────────────────────────────────
function ComplianceTab() {
  const [health, setHealth] = useState(null)
  const [rules, setRules] = useState([])
  const [checkResult, setCheckResult] = useState(null)
  const [form, setForm] = useState({ content_type: 'blog', platform: 'wordpress', content_text: '' })
  const [newRule, setNewRule] = useState({ platform: '', rule_name: '', rule_type: 'disclosure', pattern: '', action: 'block', description: '' })
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [h, r] = await Promise.all([
        api('/compliance/health', { viewer: true }),
        api('/compliance/rules', { viewer: true }),
      ])
      setHealth(h); setRules(r)
    } catch (e) { setStatus(e.message) }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const runCheck = async () => {
    setLoading(true); setStatus('Checking...')
    try {
      const r = await api('/compliance/check', { method: 'POST', body: form })
      setCheckResult(r)
      setStatus(r.passed ? '✅ All checks passed' : '❌ Compliance failed')
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const toggleRule = async (id) => {
    try {
      await api(`/compliance/rules/${id}/toggle`, { method: 'PUT' })
      loadData()
    } catch (e) { setStatus(e.message) }
  }

  const addRule = async () => {
    if (!newRule.platform || !newRule.rule_name || !newRule.pattern) return
    setLoading(true)
    try {
      await api('/compliance/rules', { method: 'POST', body: newRule })
      setNewRule({ platform: '', rule_name: '', rule_type: 'disclosure', pattern: '', action: 'block', description: '' })
      loadData(); setStatus('Rule added')
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6">
      <p className="rounded-lg bg-white p-3 text-sm text-slate-600 shadow-sm">{status || 'Compliance enforcement engine'}</p>

      {/* Health Score */}
      {health && (
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">Compliance Health Score</h2>
          <div className="flex items-center gap-6">
            <div className="relative h-24 w-24">
              <svg className="h-24 w-24 -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="#e2e8f0" strokeWidth="3" />
                <circle cx="18" cy="18" r="15.5" fill="none" stroke={health.health_score >= 90 ? '#059669' : health.health_score >= 70 ? '#d97706' : '#dc2626'} strokeWidth="3" strokeDasharray={`${health.health_score}, 100`} strokeLinecap="round" />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-xl font-bold">{health.health_score}%</span>
            </div>
            <div className="text-sm space-y-1">
              <p><span className="font-medium">Status:</span> <Badge color={health.status === 'healthy' ? 'green' : health.status === 'warning' ? 'yellow' : 'red'}>{health.status}</Badge></p>
              <p><span className="font-medium">Checks:</span> {health.total_compliance_checks} total · {health.failed_checks} failed</p>
              <p><span className="font-medium">Rules:</span> {health.active_rules} active / {health.total_rules} total</p>
              <p><span className="font-medium">Strict mode:</span> {health.strict_mode ? '✅ On' : '❌ Off'}</p>
            </div>
          </div>
        </div>
      )}

      {/* Run Compliance Check */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Run Compliance Check</h2>
        <div className="space-y-3">
          <div className="flex gap-3">
            <select className="rounded-lg border p-2 text-sm" value={form.content_type} onChange={e => setForm(f => ({ ...f, content_type: e.target.value }))}>
              <option value="blog">Blog</option>
              <option value="social">Social</option>
              <option value="newsletter">Newsletter</option>
            </select>
            <select className="rounded-lg border p-2 text-sm" value={form.platform} onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}>
              <option value="wordpress">WordPress</option>
              <option value="twitter">Twitter</option>
              <option value="linkedin">LinkedIn</option>
              <option value="medium">Medium</option>
              <option value="amazon">Amazon</option>
            </select>
          </div>
          <textarea className="w-full rounded-lg border p-2 text-sm" rows={4} placeholder="Paste content to check..." value={form.content_text} onChange={e => setForm(f => ({ ...f, content_text: e.target.value }))} />
          <Btn onClick={runCheck} disabled={loading || !form.content_text} color="indigo">Check Compliance</Btn>
          {checkResult && (
            <div className="mt-3 space-y-2">
              <p className={`font-medium ${checkResult.passed ? 'text-green-600' : 'text-red-600'}`}>
                {checkResult.passed ? '✅ PASSED' : '❌ FAILED'}
              </p>
              {checkResult.checks.map((c, i) => (
                <div key={i} className={`rounded-lg border p-2 text-sm ${c.passed ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
                  <span className="font-medium">{c.rule}</span> {!c.passed && <span className="text-red-600">— {c.reason}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Compliance Rules */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Compliance Rules ({rules.length})</h2>
        {rules.length === 0 ? <p className="text-sm text-slate-400">No rules yet.</p> : (
          <div className="max-h-80 overflow-y-auto space-y-2">
            {rules.map(r => (
              <div key={r.id} className="flex items-center justify-between border-b pb-2 text-sm">
                <div>
                  <span className="font-medium">{r.rule_name}</span>
                  <div className="text-slate-500">{r.platform} · {r.rule_type} · {r.action}</div>
                </div>
                <button onClick={() => toggleRule(r.id)} className={`rounded-lg px-3 py-1 text-xs font-medium ${r.enabled ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                  {r.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Rule */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Add Custom Rule</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <input className="rounded-lg border p-2 text-sm" placeholder="Platform (e.g. twitter)" value={newRule.platform} onChange={e => setNewRule(r => ({ ...r, platform: e.target.value }))} />
          <input className="rounded-lg border p-2 text-sm" placeholder="Rule name" value={newRule.rule_name} onChange={e => setNewRule(r => ({ ...r, rule_name: e.target.value }))} />
          <select className="rounded-lg border p-2 text-sm" value={newRule.rule_type} onChange={e => setNewRule(r => ({ ...r, rule_type: e.target.value }))}>
            <option value="disclosure">Disclosure</option>
            <option value="claim">Claim</option>
            <option value="spam">Spam</option>
            <option value="policy">Policy</option>
          </select>
          <input className="rounded-lg border p-2 text-sm" placeholder="Pattern (regex)" value={newRule.pattern} onChange={e => setNewRule(r => ({ ...r, pattern: e.target.value }))} />
          <select className="rounded-lg border p-2 text-sm" value={newRule.action} onChange={e => setNewRule(r => ({ ...r, action: e.target.value }))}>
            <option value="block">Block</option>
            <option value="warn">Warn</option>
            <option value="flag">Flag</option>
          </select>
          <input className="rounded-lg border p-2 text-sm" placeholder="Description (optional)" value={newRule.description} onChange={e => setNewRule(r => ({ ...r, description: e.target.value }))} />
        </div>
        <Btn onClick={addRule} disabled={loading || !newRule.platform || !newRule.rule_name || !newRule.pattern} color="indigo" className="mt-3">Add Rule</Btn>
      </div>
    </div>
  )
}

// 3 ─── Audit Log Viewer ──────────────────────────────────────────────
function AuditLogTab() {
  const [logs, setLogs] = useState([])
  const [filterAction, setFilterAction] = useState('')
  const [filterEntity, setFilterEntity] = useState('')
  const [recentOnly, setRecentOnly] = useState(false)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const loadLogs = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterAction) params.set('action', filterAction)
      if (filterEntity) params.set('entity_type', filterEntity)
      const path = recentOnly ? '/audit-logs/recent?minutes=1440' : `/audit-logs?${params.toString()}`
      const data = await api(path, { viewer: false })
      setLogs(Array.isArray(data) ? data : [])
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }, [filterAction, filterEntity, recentOnly])

  useEffect(() => { loadLogs() }, [loadLogs])

  return (
    <div className="space-y-6">
      <p className="rounded-lg bg-white p-3 text-sm text-slate-600 shadow-sm">{status || 'System audit trail'}</p>
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Filters</h2>
        <div className="flex flex-wrap gap-3">
          <input className="rounded-lg border p-2 text-sm w-48" placeholder="Action (e.g. market_scan)" value={filterAction} onChange={e => setFilterAction(e.target.value)} />
          <input className="rounded-lg border p-2 text-sm w-48" placeholder="Entity type (e.g. Product)" value={filterEntity} onChange={e => setFilterEntity(e.target.value)} />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={recentOnly} onChange={e => setRecentOnly(e.target.checked)} className="rounded" />
            Last 24h only
          </label>
          <Btn onClick={loadLogs} disabled={loading} color="sky">Search</Btn>
        </div>
      </div>

      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Audit Logs ({logs.length})</h2>
        {loading ? <LoadingSpinner /> : logs.length === 0 ? <p className="text-sm text-slate-400">No logs found.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-slate-500">
                  <th className="pb-2 pr-3">Time</th>
                  <th className="pb-2 pr-3">Action</th>
                  <th className="pb-2 pr-3">Entity</th>
                  <th className="pb-2 pr-3">Details</th>
                  <th className="pb-2 pr-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id} className="border-b last:border-0 hover:bg-slate-50">
                    <td className="py-2 pr-3 whitespace-nowrap text-slate-500">{new Date(log.created_at).toLocaleString()}</td>
                    <td className="py-2 pr-3"><code className="rounded bg-slate-100 px-1">{log.action}</code></td>
                    <td className="py-2 pr-3">{log.entity_type}{log.entity_id ? ` #${log.entity_id}` : ''}</td>
                    <td className="py-2 pr-3 max-w-xs truncate">{log.details}</td>
                    <td className="py-2 pr-3"><Badge color={log.success ? 'green' : 'red'}>{log.success ? 'OK' : 'FAIL'}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// 4 ─── Content Management ────────────────────────────────────────────
function ContentTab() {
  const [pending, setPending] = useState([])
  const [published, setPublished] = useState([])
  const [products, setProducts] = useState([])
  const [selectedProduct, setSelectedProduct] = useState('')
  const [category, setCategory] = useState('default')
  const [generated, setGenerated] = useState(null)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [p, pub, prod] = await Promise.all([
        api('/content/pending', { viewer: true }),
        api('/content/published', { viewer: true }),
        api('/report', { viewer: true }).then(r => r.daily_earnings || []).catch(() => []),
      ])
      setPending(Array.isArray(p) ? p : [])
      setPublished(Array.isArray(pub) ? pub : [])
    } catch (e) { setStatus(e.message) }
  }, [])

  const loadProducts = useCallback(async () => {
    try {
      const r = await api('/scan', { method: 'POST' })
      setProducts(r.products)
      if (r.products.length && !selectedProduct) setSelectedProduct(String(r.products[0].id))
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const generateBlog = async () => {
    if (!selectedProduct) return
    setLoading(true); setStatus('Generating...')
    try {
      const r = await api(`/content/generate/blog?product_id=${selectedProduct}&category=${category}`, { method: 'POST' })
      setGenerated(r)
      setStatus('Blog content generated')
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const createDraft = async () => {
    if (!generated) return
    setLoading(true); setStatus('Creating draft...')
    try {
      await api('/content/draft', { method: 'POST', body: { title: generated.title, content_type: 'blog', platform: 'wordpress', body: generated.body } })
      setStatus('Draft created!')
      loadData()
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const publishDraft = async (id) => {
    setLoading(true)
    try {
      await api('/content/publish', { method: 'POST', body: { content_id: id } })
      setStatus('Content published!')
      loadData()
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6">
      <p className="rounded-lg bg-white p-3 text-sm text-slate-600 shadow-sm">{status || 'Content generation and publishing'}</p>

      {/* Generate Content */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Generate Blog Content</h2>
        <div className="flex flex-wrap gap-3 mb-3">
          <Btn onClick={loadProducts} color="slate" size="sm">Load Products</Btn>
          <select className="rounded-lg border p-2 text-sm flex-1 min-w-[200px]" value={selectedProduct} onChange={e => setSelectedProduct(e.target.value)}>
            <option value="">Select a product...</option>
            {products.map(p => <option key={p.id} value={p.id}>{p.name} ({p.network})</option>)}
          </select>
          <select className="rounded-lg border p-2 text-sm" value={category} onChange={e => setCategory(e.target.value)}>
            <option value="default">Default</option>
            <option value="tech">Tech</option>
            <option value="fitness">Fitness</option>
            <option value="finance">Finance</option>
          </select>
          <Btn onClick={generateBlog} disabled={loading || !selectedProduct} color="indigo">Generate</Btn>
        </div>

        {generated && (
          <div className="mt-3 space-y-3 rounded-lg border p-3">
            <h3 className="font-semibold">{generated.title}</h3>
            <pre className="max-h-60 overflow-y-auto whitespace-pre-wrap text-xs text-slate-600">{generated.body}</pre>
            <Btn onClick={createDraft} disabled={loading} color="green" size="sm">Create Draft</Btn>
          </div>
        )}
      </div>

      {/* Pending Drafts */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Pending Drafts ({pending.length})</h2>
        {pending.length === 0 ? <p className="text-sm text-slate-400">No pending drafts.</p> : (
          <div className="space-y-2">
            {pending.map(d => (
              <div key={d.id} className="flex items-center justify-between border-b pb-2 text-sm">
                <div>
                  <span className="font-medium">{d.title}</span>
                  <div className="text-slate-500">{d.platform} · <Badge color={d.compliance_passed ? 'green' : 'yellow'}>{d.compliance_passed ? 'Compliant' : 'Pending'}</Badge></div>
                </div>
                <div className="flex gap-2">
                  <Badge color={d.status === 'draft' ? 'blue' : 'purple'}>{d.status}</Badge>
                  <Btn onClick={() => publishDraft(d.id)} disabled={loading} color="green" size="sm">Publish</Btn>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Published */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Published Content ({published.length})</h2>
        {published.length === 0 ? <p className="text-sm text-slate-400">No published content yet.</p> : (
          <div className="space-y-2">
            {published.map(d => (
              <div key={d.id} className="flex items-center justify-between border-b pb-2 text-sm">
                <div>
                  <span className="font-medium">{d.title}</span>
                  <div className="text-slate-500">{d.platform} · {d.external_post_id && <code className="text-xs">{d.external_post_id}</code>}</div>
                </div>
                <span className="text-xs text-slate-400">{new Date(d.published_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// 5 ─── Notification Center ──────────────────────────────────────────
function NotificationTab() {
  const [notifications, setNotifications] = useState([])
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const path = unreadOnly ? '/notifications?unread_only=true' : '/notifications'
      const data = await api(path, { viewer: true })
      setNotifications(Array.isArray(data) ? data : [])
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }, [unreadOnly])

  useEffect(() => { load() }, [load])

  const markRead = async (id) => {
    try { await api(`/notifications/${id}/read`, { method: 'PUT', viewer: true }); load() }
    catch (e) { setStatus(e.message) }
  }

  const markAllRead = async () => {
    try { await api('/notifications/read-all', { method: 'PUT', viewer: true }); load() }
    catch (e) { setStatus(e.message) }
  }

  const severityColor = (s) => ({ info: 'blue', warning: 'yellow', critical: 'red' })[s] || 'slate'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg bg-white p-3 shadow-sm">
        <p className="text-sm text-slate-600">{status || `${notifications.length} notifications`}</p>
        <div className="flex gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={unreadOnly} onChange={e => setUnreadOnly(e.target.checked)} className="rounded" />
            Unread only
          </label>
          <Btn onClick={load} disabled={loading} color="sky" size="sm">Refresh</Btn>
          <Btn onClick={markAllRead} disabled={loading} color="indigo" size="sm">Mark All Read</Btn>
        </div>
      </div>

      <div className="space-y-2">
        {loading ? <LoadingSpinner /> : notifications.length === 0 ? (
          <p className="rounded-xl bg-white p-8 text-center text-sm text-slate-400">No notifications.</p>
        ) : notifications.map(n => (
          <div key={n.id} className={`rounded-xl border p-4 shadow-sm ${n.is_read ? 'bg-white' : 'bg-indigo-50 border-indigo-200'}`}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{n.title}</span>
                  <Badge color={severityColor(n.severity)}>{n.severity}</Badge>
                  <Badge color={n.notification_type === 'compliance_alert' ? 'red' : 'blue'}>{n.notification_type}</Badge>
                </div>
                <p className="mt-1 text-sm text-slate-600">{n.message}</p>
                <p className="mt-1 text-xs text-slate-400">{new Date(n.created_at).toLocaleString()}</p>
              </div>
              {!n.is_read && <Btn onClick={() => markRead(n.id)} color="indigo" size="sm">Mark Read</Btn>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// 6 ─── Commission Forecasting ────────────────────────────────────────
function ForecastTab() {
  const [forecast, setForecast] = useState(null)
  const [trends, setTrends] = useState(null)
  const [summary, setSummary] = useState(null)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [f, t, s] = await Promise.all([
        api('/forecast?period=monthly&months=3', { viewer: true }),
        api('/forecast/trends', { viewer: true }),
        api('/forecast/summary', { viewer: true }),
      ])
      setForecast(f); setTrends(t); setSummary(s)
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg bg-white p-3 shadow-sm">
        <p className="text-sm text-slate-600">{status || 'Commission forecasting & trends'}</p>
        <Btn onClick={loadAll} disabled={loading} color="sky" size="sm">Refresh</Btn>
      </div>

      {loading ? <LoadingSpinner /> : (
        <>
          {/* Summary Cards */}
          {summary && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card title="Current Month" value={`$${(summary.current_month_earnings || 0).toFixed(2)}`} color="blue" />
              <Card title="Next Month (projected)" value={`$${(summary.next_month_projection || 0).toFixed(2)}`} color="green" />
              <Card title="Quarter Projection" value={`$${(summary.quarter_projection || 0).toFixed(2)}`} color="purple" />
              <Card title="Trend" value={summary.trend || '—'} color={summary.trend === 'growing' ? 'green' : summary.trend === 'declining' ? 'red' : 'yellow'} />
            </div>
          )}

          {/* Trends */}
          {trends && (
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold">Trends &amp; Metrics</h2>
              <div className="grid gap-4 sm:grid-cols-3 text-sm">
                <div><span className="text-slate-500">Total earnings:</span> <span className="font-semibold">${trends.total_earnings?.toFixed(2)}</span></div>
                <div><span className="text-slate-500">30-day earnings:</span> <span className="font-semibold">${trends.recent_30_days_earnings?.toFixed(2)}</span></div>
                <div><span className="text-slate-500">Period change:</span> <span className={`font-semibold ${trends.period_change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>{trends.period_change_pct > 0 ? '+' : ''}{trends.period_change_pct}%</span></div>
                <div><span className="text-slate-500">Avg commission:</span> <span className="font-semibold">${trends.average_commission_value?.toFixed(2)}</span></div>
                <div><span className="text-slate-500">Conversion rate:</span> <span className="font-semibold">{trends.conversion_rate}%</span></div>
                <div><span className="text-slate-500">Projected monthly:</span> <span className="font-semibold">${trends.projected_monthly?.toFixed(2)}</span></div>
              </div>
            </div>
          )}

          {/* Forecast Chart */}
          {forecast && forecast.forecast && forecast.forecast.length > 0 && (
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold">Forecast ({forecast.forecast_periods} {forecast.period_type})</h2>
              <div className="mb-2 text-sm text-slate-500">
                Trend: <span className={`font-semibold ${forecast.trend_direction === 'upward' ? 'text-green-600' : forecast.trend_direction === 'downward' ? 'text-red-600' : ''}`}>{forecast.trend_direction}</span>
                {' · '}Confidence: <Badge color={forecast.confidence === 'high' ? 'green' : forecast.confidence === 'medium' ? 'yellow' : 'red'}>{forecast.confidence}</Badge>
              </div>
              <MiniBar data={forecast.forecast} labelKey="period" valueKey="predicted_earnings" color="#6366f1" />
              <div className="mt-2 grid gap-2 sm:grid-cols-3 text-xs text-slate-500">
                {forecast.forecast.map((f, i) => (
                  <div key={i} className="rounded-lg border p-2">
                    <span className="font-semibold">{f.period}</span>
                    <div>Predicted: <span className="font-mono">${f.predicted_earnings}</span></div>
                    <div>Range: ${f.lower_bound} – ${f.upper_bound}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Insights */}
          {summary && summary.insights && summary.insights.length > 0 && (
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold">AI Insights</h2>
              <ul className="space-y-2">
                {summary.insights.map((insight, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="mt-0.5 text-indigo-500">💡</span>
                    <span>{insight}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// 7 ─── Multi-Network Dashboard ──────────────────────────────────────
function NetworkTab() {
  const [byNetwork, setByNetwork] = useState([])
  const [timeline, setTimeline] = useState([])
  const [byChannel, setByChannel] = useState([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [n, t, c] = await Promise.all([
        api('/earnings/by-network', { viewer: true }),
        api('/earnings/timeline?days=30', { viewer: true }),
        api('/earnings/by-channel', { viewer: true }),
      ])
      setByNetwork(Array.isArray(n) ? n : [])
      setTimeline(Array.isArray(t) ? t : [])
      setByChannel(Array.isArray(c) ? c : [])
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  const totalEarnings = byNetwork.reduce((s, n) => s + n.total_earnings, 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg bg-white p-3 shadow-sm">
        <p className="text-sm text-slate-600">{status || 'Earnings breakdown by network'}</p>
        <Btn onClick={loadAll} disabled={loading} color="sky" size="sm">Refresh</Btn>
      </div>

      {loading ? <LoadingSpinner /> : (
        <>
          {/* By Network */}
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Earnings by Network (Total: ${totalEarnings.toFixed(2)})</h2>
            {byNetwork.length === 0 ? <p className="text-sm text-slate-400">No data yet.</p> : (
              <div className="space-y-3">
                {byNetwork.map(n => (
                  <div key={n.network} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <span className="font-semibold">{n.network}</span>
                      <div className="text-xs text-slate-500">{n.commission_count} commissions · {n.purchase_count} purchases</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">${n.total_earnings.toFixed(2)}</div>
                      <div className="text-xs text-slate-500">avg ${n.average_commission.toFixed(2)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Timeline */}
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Earnings Timeline (30 days)</h2>
            <MiniBar data={timeline} labelKey="date" valueKey="earnings" color="#0891b2" />
          </div>

          {/* By Channel */}
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Performance by Channel</h2>
            {byChannel.length === 0 ? <p className="text-sm text-slate-400">No data yet.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b text-slate-500">
                      <th className="pb-2 pr-3">Platform</th>
                      <th className="pb-2 pr-3">Clicks</th>
                      <th className="pb-2 pr-3">Conversions</th>
                      <th className="pb-2 pr-3">Conversion Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byChannel.map(c => (
                      <tr key={c.platform} className="border-b last:border-0">
                        <td className="py-2 pr-3 font-medium">{c.platform}</td>
                        <td className="py-2 pr-3">{c.clicks}</td>
                        <td className="py-2 pr-3">{c.conversions}</td>
                        <td className="py-2 pr-3"><Badge color={c.conversion_rate > 5 ? 'green' : c.conversion_rate > 1 ? 'yellow' : 'red'}>{c.conversion_rate}%</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// 8 ─── Social Account Management ────────────────────────────────────
function SocialAccountTab() {
  const [accounts, setAccounts] = useState([])
  const [newAccount, setNewAccount] = useState({ platform: '', account_name: '', alias: '', access_token: '', api_key: '', api_secret: '', username: '', password: '' })
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({ account_name: '', alias: '' })
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const loadAccounts = useCallback(async () => {
    try {
      const data = await api('/social-accounts', { viewer: true })
      setAccounts(Array.isArray(data) ? data : [])
    } catch (e) { setStatus(e.message) }
  }, [])

useEffect(() => { loadAccounts() }, [loadAccounts])

  const addAccount = async () => {
    if (!newAccount.platform || !newAccount.account_name) return
    setLoading(true)
    try {
      // Build credentials payload supporting both API keys and username/password
      const credentials = {}
      if (newAccount.access_token) credentials.access_token = newAccount.access_token
      if (newAccount.api_key) credentials.api_key = newAccount.api_key
      if (newAccount.api_secret) credentials.api_secret = newAccount.api_secret
      if (newAccount.username) credentials.username = newAccount.username
      if (newAccount.password) credentials.password = newAccount.password

      const payload = {
        platform: newAccount.platform,
        account_name: newAccount.alias || newAccount.account_name,
        credentials,
      }
      await api('/social-accounts', { method: 'POST', body: payload })
      setNewAccount({ platform: '', account_name: '', alias: '', access_token: '', api_key: '', api_secret: '', username: '', password: '' })
      loadAccounts()
      setStatus('Account connected')
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const startEdit = (a) => {
    setEditingId(a.id)
    setEditForm({ account_name: a.account_name, alias: a.account_name })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditForm({ account_name: '', alias: '' })
  }

  const saveEdit = async () => {
    if (!editingId) return
    setLoading(true)
    try {
      await api(`/social-accounts/${editingId}`, {
        method: 'PUT',
        body: { account_name: editForm.alias || editForm.account_name },
      })
      setEditingId(null)
      setEditForm({ account_name: '', alias: '' })
      loadAccounts()
      setStatus('Account updated')
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const verifyAccount = async (id) => {
    setLoading(true)
    try {
      const r = await api(`/social-accounts/${id}/verify`, { method: 'POST' })
      setStatus(r.status || 'Verification initiated')
      loadAccounts()
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const deleteAccount = async (id) => {
    if (!confirm('Delete this account?')) return
    setLoading(true)
    try {
      await api(`/social-accounts/${id}`, { method: 'DELETE' })
      loadAccounts()
      setStatus('Account deleted')
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const triggerSync = async (id) => {
    setLoading(true)
    try {
      const r = await api(`/social-accounts/${id}/sync`, { method: 'POST' })
      setStatus(r.status || 'Sync triggered')
      loadAccounts()
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6">
      <p className="rounded-lg bg-white p-3 text-sm text-slate-600 shadow-sm">{status || 'Manage connected social accounts'}</p>

{/* Add Account Form */}
      <div className="neu-card p-4">
        <h2 className="mb-3 text-lg font-semibold text-slate-800">Connect Social Account</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <select className="neu-input px-3 py-2 text-sm" value={newAccount.platform} onChange={e => setNewAccount(a => ({ ...a, platform: e.target.value }))}>
            <option value="">Select platform...</option>
            <option value="twitter">Twitter / X</option>
            <option value="facebook">Facebook</option>
            <option value="linkedin">LinkedIn</option>
            <option value="instagram">Instagram</option>
            <option value="wordpress">WordPress</option>
            <option value="mailchimp">Mailchimp</option>
            <option value="medium">Medium</option>
            <option value="tiktok">TikTok</option>
            <option value="telegram">Telegram</option>
            <option value="discord">Discord</option>
            <option value="other">Other</option>
          </select>
          <input className="neu-input px-3 py-2 text-sm" placeholder="Account name (e.g. @MyBrand)" value={newAccount.account_name} onChange={e => setNewAccount(a => ({ ...a, account_name: e.target.value }))} />
          <input className="neu-input px-3 py-2 text-sm" placeholder="Custom alias for tracking (e.g. Twitter-Tech)" value={newAccount.alias} onChange={e => setNewAccount(a => ({ ...a, alias: e.target.value }))} />
          <input className="neu-input px-3 py-2 text-sm" placeholder="Username / email" value={newAccount.username} onChange={e => setNewAccount(a => ({ ...a, username: e.target.value }))} />
          <input className="neu-input px-3 py-2 text-sm" type="password" placeholder="Password" value={newAccount.password} onChange={e => setNewAccount(a => ({ ...a, password: e.target.value }))} />
          <input className="neu-input px-3 py-2 text-sm" placeholder="Access token (API)" value={newAccount.access_token} onChange={e => setNewAccount(a => ({ ...a, access_token: e.target.value }))} />
          <input className="neu-input px-3 py-2 text-sm" placeholder="API key (optional)" value={newAccount.api_key} onChange={e => setNewAccount(a => ({ ...a, api_key: e.target.value }))} />
          <input className="neu-input px-3 py-2 text-sm" placeholder="API secret (optional)" value={newAccount.api_secret} onChange={e => setNewAccount(a => ({ ...a, api_secret: e.target.value }))} />
        </div>
        <p className="mt-2 text-xs text-slate-500">🔒 Credentials are encrypted and stored securely. Provide either username/password <em>or</em> API credentials.</p>
        <Btn onClick={addAccount} disabled={loading || !newAccount.platform || !newAccount.account_name} color="indigo" className="mt-3">Connect Account</Btn>
      </div>

{/* Existing Accounts */}
      <div className="neu-card p-4">
        <h2 className="mb-3 text-lg font-semibold text-slate-800">Connected Accounts ({accounts.length})</h2>
        {accounts.length === 0 ? <p className="text-sm text-slate-400">No accounts connected yet.</p> : (
          <div className="space-y-3">
            {accounts.map(a => (
              <div key={a.id}>
                {editingId === a.id ? (
                  /* Inline edit form */
                  <div className="neu-inset-soft p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Edit alias</span>
                      <input className="neu-input px-3 py-1.5 text-sm flex-1 min-w-[180px]" value={editForm.alias} onChange={e => setEditForm(f => ({ ...f, alias: e.target.value }))} placeholder="Custom alias" />
                      <Btn onClick={saveEdit} disabled={loading} color="green" size="sm">Save</Btn>
                      <Btn onClick={cancelEdit} disabled={loading} color="slate" size="sm">Cancel</Btn>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between border-b pb-3 text-sm">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{a.account_name}</span>
                        <Badge color={a.connection_status === 'active' ? 'green' : a.connection_status === 'expired' ? 'yellow' : a.connection_status === 'suspended' ? 'red' : 'slate'}>{a.connection_status}</Badge>
                        <Badge color="blue">{a.platform}</Badge>
                      </div>
                      <div className="text-xs text-slate-500">
                        {a.is_verified ? '✅ Verified' : '❌ Not verified'} · {a.total_posts || 0} posts · {a.last_sync_at ? `Last sync: ${new Date(a.last_sync_at).toLocaleDateString()}` : 'Never synced'}
                      </div>
                      {a.connection_status === 'expired' && (
                        <div className="mt-1 text-xs font-medium text-amber-600">⚠️ Re-authentication required</div>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Btn onClick={() => startEdit(a)} disabled={loading} color="slate" size="sm">Edit</Btn>
                      <Btn onClick={() => triggerSync(a.id)} disabled={loading} color="sky" size="sm">Sync</Btn>
                      <Btn onClick={() => verifyAccount(a.id)} disabled={loading} color="sky" size="sm">Verify</Btn>
                      <Btn onClick={() => deleteAccount(a.id)} color="red" size="sm">Delete</Btn>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// 9 ─── Posting Queue
function PostingQueueTab() {
  const [queue, setQueue] = useState([])
  const [mode, setMode] = useState({ mode: 'manual' })
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const [filterStatus, setFilterStatus] = useState('')

  const loadAll = useCallback(async () => {
    try {
      const params = filterStatus ? `?status=${filterStatus}` : ''
      const [q, m] = await Promise.all([
        api(`/posting-queue${params}`, { viewer: true }),
        api('/posting-mode', { viewer: true }),
      ])
      setQueue(Array.isArray(q) ? q : [])
      setMode(m)
    } catch (e) { setStatus(e.message) }
  }, [filterStatus])

  useEffect(() => { loadAll() }, [loadAll])

  const toggleMode = async () => {
    const newMode = mode.mode === 'auto' ? 'manual' : 'auto'
    setLoading(true)
    try {
      const r = await api('/posting-mode', { method: 'PUT', body: { mode: newMode } })
      setMode(r)
      setStatus(`Mode switched to ${newMode}`)
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const approveItem = async (id) => {
    setLoading(true)
    try {
      await api(`/posting-queue/${id}/approve`, { method: 'POST', body: { queue_id: id } })
      loadAll(); setStatus('Approved!')
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const rejectItem = async (id) => {
    setLoading(true)
    try {
      await api(`/posting-queue/${id}/reject`, { method: 'POST', body: { queue_id: id } })
      loadAll(); setStatus('Rejected.')
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }

  const statusColor = (s) => ({ queued: 'yellow', approved: 'blue', published: 'green', rejected: 'red', failed: 'red', already_queued: 'purple' })[s] || 'slate'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg bg-white p-3 shadow-sm">
        <p className="text-sm text-slate-600">{status || `${queue.length} queue items`}</p>
        <div className="flex gap-2">
          <Btn onClick={toggleMode} disabled={loading} color={mode.mode === 'auto' ? 'green' : 'yellow'} size="sm">
            Mode: {mode.mode.toUpperCase()}
          </Btn>
          <select className="rounded-lg border p-1 text-xs" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
            <option value="">All</option>
            <option value="queued">Queued</option>
            <option value="approved">Approved</option>
            <option value="published">Published</option>
            <option value="rejected">Rejected</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      <div className="space-y-2">
        {queue.length === 0 ? <p className="rounded-xl bg-white p-8 text-center text-sm text-slate-400">No queue items.</p> : queue.map(item => (
          <div key={item.id} className="rounded-xl bg-white p-4 shadow-sm flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold">{item.content_title || `Draft #${item.content_draft_id}`}</span>
                <Badge color={statusColor(item.status)}>{item.status}</Badge>
                <Badge color={item.posting_mode === 'auto' ? 'green' : 'blue'}>{item.posting_mode}</Badge>
              </div>
              <div className="text-sm text-slate-500">{item.account_name} · {item.platform}</div>
              <div className="text-xs text-slate-400">Queued: {new Date(item.queued_at).toLocaleString()}</div>
            </div>
            {item.status === 'queued' && (
              <div className="flex gap-2">
                <Btn onClick={() => approveItem(item.id)} disabled={loading} color="green" size="sm">Approve</Btn>
                <Btn onClick={() => rejectItem(item.id)} disabled={loading} color="red" size="sm">Reject</Btn>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// 10 ─── System Logs (Real-Time) ───────────────────────────────────────
function SystemLogsTab() {
  const [logs, setLogs] = useState([])
  const [filterCategory, setFilterCategory] = useState('')
  const [categoryCounts, setCategoryCounts] = useState([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const [isLive, setIsLive] = useState(false)
  const [newLogCount, setNewLogCount] = useState(0)
  const logsEndRef = useRef(null)
  const eventSourceRef = useRef(null)
  const prevLogCountRef = useRef(0)

  const CATEGORIES = [
    { value: '', label: 'All Categories', color: 'slate' },
    { value: 'scanning', label: '🔄 Scanning', color: 'blue' },
    { value: 'validation', label: '✅ Validation', color: 'green' },
    { value: 'posting', label: '📤 Posting', color: 'purple' },
    { value: 'payment', label: '💰 Payment', color: 'emerald' },
    { value: 'compliance', label: '🛡️ Compliance', color: 'amber' },
    { value: 'system', label: '⚙️ System', color: 'slate' },
  ]

  const loadInitialLogs = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterCategory) params.set('action_category', filterCategory)
      params.set('limit', '200')
      const data = await api(`/audit-logs?${params.toString()}`, { viewer: true })
      setLogs(Array.isArray(data) ? data : [])
      prevLogCountRef.current = Array.isArray(data) ? data.length : 0

      // Load category counts
      const cats = await api('/logs/categories', { viewer: true })
      setCategoryCounts(cats.categories || [])
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }, [filterCategory])

  useEffect(() => { loadInitialLogs() }, [loadInitialLogs])

  // Auto-scroll to bottom
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs.length])

  // SSE connection for live updates
  useEffect(() => {
    if (!isLive) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      return
    }

    const params = new URLSearchParams()
    if (filterCategory) params.set('action_category', filterCategory)
    const url = `${API_BASE}/logs/stream?${params.toString()}`

    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onmessage = (event) => {
      try {
        const logEntry = JSON.parse(event.data)
        setLogs(prev => {
          // Don't add duplicates
          if (prev.some(l => l.id === logEntry.id)) return prev
          const updated = [logEntry, ...prev].slice(0, 500) // keep max 500
          return updated
        })
        setNewLogCount(prev => prev + 1)

        // Update category counts
        if (logEntry.action_category) {
          setCategoryCounts(prev => {
            const updated = [...prev]
            const idx = updated.findIndex(c => c.category === logEntry.action_category)
            if (idx >= 0) {
              updated[idx] = { ...updated[idx], count: updated[idx].count + 1 }
            } else {
              updated.push({ category: logEntry.action_category, count: 1 })
            }
            return updated
          })
        }
      } catch (e) { /* ignore parse errors */ }
    }

    es.onerror = () => {
      // Reconnect logic - EventSource handles this automatically
      setStatus('Live stream disconnected. Reconnecting...')
    }

    return () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [isLive, filterCategory])

  // Clear new log count when user focuses the tab
  const handleFocus = () => {
    setNewLogCount(0)
  }

  const categoryColor = (cat) => {
    const found = CATEGORIES.find(c => c.value === cat)
    return found ? found.color : 'slate'
  }

  const getCategoryCount = (cat) => {
    const found = categoryCounts.find(c => c.category === cat)
    return found ? found.count : 0
  }

  return (
    <div className="space-y-6" onClick={handleFocus}>
      {/* Header with live toggle */}
      <div className="flex items-center justify-between rounded-lg bg-white p-3 shadow-sm">
        <div className="flex items-center gap-3">
          <p className="text-sm text-slate-600">{status || `${logs.length} log entries`}</p>
          {isLive && (
            <span className="flex items-center gap-1 text-xs font-medium text-green-600">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-green-500" />
              LIVE
            </span>
          )}
          {newLogCount > 0 && isLive && (
            <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">
              +{newLogCount} new
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setIsLive(!isLive)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              isLive
                ? 'bg-green-100 text-green-700 ring-1 ring-green-300'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {isLive ? '🔴 Stop Live' : '▶️ Live Stream'}
          </button>
          <Btn onClick={loadInitialLogs} disabled={loading} color="sky" size="sm">Refresh</Btn>
        </div>
      </div>

      {/* Category filter pills */}
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map(cat => (
          <button
            key={cat.value}
            onClick={() => { setFilterCategory(cat.value); setNewLogCount(0) }}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
              filterCategory === cat.value
                ? 'bg-indigo-600 text-white ring-2 ring-indigo-300'
                : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:ring-indigo-300'
            }`}
          >
            {cat.label}
            <span className="ml-1.5 rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-mono">
              {getCategoryCount(cat.value)}
            </span>
          </button>
        ))}
      </div>

      {/* Log entries */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">System Activity Log</h2>
        {loading ? <LoadingSpinner /> : logs.length === 0 ? (
          <p className="text-center py-8 text-sm text-slate-400">No log entries found. Toggle Live Stream to see events in real time.</p>
        ) : (
          <div className="max-h-[600px] overflow-y-auto space-y-1">
            {logs.map((log, idx) => (
              <div
                key={log.id || idx}
                className={`flex items-start gap-3 rounded-lg p-2.5 text-sm transition-colors hover:bg-slate-50 ${
                  idx === 0 && isLive ? 'bg-indigo-50/50' : ''
                }`}
              >
                {/* Timestamp */}
                <div className="w-36 shrink-0 text-xs text-slate-400 font-mono">
                  {new Date(log.created_at).toLocaleString()}
                </div>

                {/* Category badge */}
                <div className="w-20 shrink-0">
                  <Badge color={categoryColor(log.action_category)}>
                    {log.action_category || 'system'}
                  </Badge>
                </div>

                {/* Action */}
                <div className="w-36 shrink-0">
                  <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-700">
                    {log.action}
                  </code>
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  <span className="text-slate-600 truncate block">{log.details || '—'}</span>
                  {log.entity_type && (
                    <span className="text-[10px] text-slate-400">
                      {log.entity_type}{log.entity_id ? ` #${log.entity_id}` : ''}
                    </span>
                  )}
                </div>

                {/* Status */}
                <div className="w-16 shrink-0 text-right">
                  <Badge color={log.success ? 'green' : 'red'}>
                    {log.success ? 'OK' : 'FAIL'}
                  </Badge>
                </div>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>
    </div>
  )
}

// 11 ─── Account Analytics ────────────────────────────────────────────
function AccountAnalyticsTab() {
  const [analytics, setAnalytics] = useState(null)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api('/analytics/accounts', { viewer: true })
      setAnalytics(data)
    } catch (e) { setStatus(e.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  if (loading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg bg-white p-3 shadow-sm">
        <p className="text-sm text-slate-600">{status || 'Per-account performance analytics'}</p>
        <Btn onClick={loadAll} disabled={loading} color="sky" size="sm">Refresh</Btn>
      </div>

      {analytics && (
        <>
          {/* Summary */}
          {analytics.total_earnings_all !== undefined && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card title="Total Earnings" value={`$${analytics.total_earnings_all.toFixed(2)}`} color="green" />
              <Card title="Total Clicks" value={String(analytics.total_clicks_all)} color="blue" />
              <Card title="Total Conversions" value={String(analytics.total_conversions_all)} color="purple" />
              <Card title="Conversion Rate" value={`${analytics.total_clicks_all ? ((analytics.total_conversions_all / analytics.total_clicks_all) * 100).toFixed(1) : '0.0'}%`} color="teal" />
            </div>
          )}

          {analytics.top_account && (
            <div className="neu-pill neu-pill--green px-4 py-2">🏆 Top account: <strong>{analytics.top_account}</strong></div>
          )}

          {analytics.accounts && analytics.accounts.length > 1 && (
            <div className="neu-inset-soft grid gap-2 p-3 sm:grid-cols-3 text-sm">
              <div>
                <span className="text-slate-500">Highest earnings:</span>{' '}
                <strong>{[...analytics.accounts].sort((a, b) => b.total_earnings - a.total_earnings)[0]?.total_earnings ? `$${[...analytics.accounts].sort((a, b) => b.total_earnings - a.total_earnings)[0].total_earnings.toFixed(2)}` : '—'}</strong>
              </div>
              <div>
                <span className="text-slate-500">Best conversion:</span>{' '}
                <strong>{[...analytics.accounts].sort((a, b) => b.conversion_rate - a.conversion_rate)[0]?.conversion_rate ? `${[...analytics.accounts].sort((a, b) => b.conversion_rate - a.conversion_rate)[0].conversion_rate}%` : '—'}</strong>
              </div>
              <div>
                <span className="text-slate-500">Accounts:</span>{' '}
                <strong>{analytics.accounts.length}</strong>
              </div>
            </div>
          )}

          {/* Per-account cards */}
          {analytics.accounts && analytics.accounts.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {analytics.accounts.map(a => (
                <div key={a.account_id} className="neu-card neu-card--hover p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-slate-800">{a.account_name}</span>
                    <Badge color={a.connection_status === 'active' ? 'green' : a.connection_status === 'expired' ? 'yellow' : a.connection_status === 'suspended' ? 'red' : 'slate'}>{a.connection_status}</Badge>
                  </div>
                  <div className="text-xs text-slate-500 mb-2">{a.platform}</div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div><span className="text-slate-500">Posts:</span> {a.total_posts}</div>
                    <div><span className="text-slate-500">Clicks:</span> {a.total_clicks}</div>
                    <div><span className="text-slate-500">Conversions:</span> {a.total_conversions}</div>
                    <div><span className="text-slate-500">Earnings:</span> ${a.total_earnings?.toFixed(2)}</div>
                    <div><span className="text-slate-500">Conversion rate:</span> {a.conversion_rate}%</div>
                    <div>
                      <span className="text-slate-500">ROI:</span>{' '}
                      <strong>{a.total_clicks ? `$${(a.total_earnings / a.total_clicks).toFixed(2)}/click` : '—'}</strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {(!analytics.accounts || analytics.accounts.length === 0) && (
            <p className="rounded-xl bg-white p-8 text-center text-sm text-slate-400">No account analytics yet. Add social accounts first.</p>
          )}
        </>
      )}
    </div>
  )
}

// ── Shared Components ────────────────────────────────────────────────

function Card({ title, value, color = 'slate' }) {
  return (
    <div className="neu-card neu-card--hover p-4">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
      <p className={`mt-1 text-2xl font-bold text-slate-800 neu-pill--${color || 'slate'}`} style={{ padding: '0.1rem 0', background: 'transparent', boxShadow: 'none' }}>{value}</p>
    </div>
  )
}

function Btn({ children, onClick, disabled, color = 'slate', size = 'md', className = '' }) {
  const sizes = { sm: 'px-2 py-1 text-xs', md: 'px-3 py-2 text-sm', lg: 'px-4 py-2 text-base' }
  const accent = color === 'indigo' || color === 'blue' || color === 'purple' ? ' neu-btn--accent' : ''
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`neu-btn${accent} ${sizes[size] || sizes.md} ${className}`}
    >
      {children}
    </button>
  )
}

// ── Tab configuration ────────────────────────────────────────────────

const TABS = [
  { id: 'overview', label: '📊 Overview', Component: OverviewTab },
  { id: 'compliance', label: '🛡️ Compliance', Component: ComplianceTab },
  { id: 'audit', label: '📋 Audit Logs', Component: AuditLogTab },
  { id: 'content', label: '📝 Content', Component: ContentTab },
  { id: 'notifications', label: '🔔 Notifications', Component: NotificationTab },
  { id: 'forecast', label: '📈 Forecast', Component: ForecastTab },
  { id: 'networks', label: '🌐 Networks', Component: NetworkTab },
  { id: 'social', label: '👤 Social Accts', Component: SocialAccountTab },
  { id: 'queue', label: '📤 Post Queue', Component: PostingQueueTab },
  { id: 'analytics', label: '📊 Acct Analytics', Component: AccountAnalyticsTab },
  { id: 'system-logs', label: '📜 System Logs', Component: SystemLogsTab },
  { id: 'morphism', label: '🧬 Morphism', Component: MorphismTab },
]

// ── Main App ─────────────────────────────────────────────────────────

export default function App() {
  const [activeTab, setActiveTab] = useState('overview')
  const [unreadNotifCount, setUnreadNotifCount] = useState(0)

  const active = TABS.find(t => t.id === activeTab) || TABS[0]

  // check backend health
  const [backendOk, setBackendOk] = useState(null)
  useEffect(() => {
    api('/report', { viewer: true })
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
  }, [])

  // Silent notification polling (non-intrusive badge update)
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const notifs = await api('/notifications?unread_only=true', { viewer: true })
        if (Array.isArray(notifs)) {
          setUnreadNotifCount(notifs.length)
        }
      } catch { /* silent */ }
    }, 15000) // every 15 seconds
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="neu-header sticky top-0 z-10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-xl font-bold text-slate-800">Affluence-AI</h1>
            <p className="text-xs text-slate-500">Autonomous Affiliate Marketing System</p>
          </div>
          <div className="flex items-center gap-4">
            {/* Silent notification badge */}
            {unreadNotifCount > 0 && (
              <button
                onClick={() => setActiveTab('notifications')}
                className="neu-pill neu-pill--indigo flex items-center gap-1 hover:opacity-80 transition-opacity"
                title={`${unreadNotifCount} unread notification${unreadNotifCount > 1 ? 's' : ''}`}
              >
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
                <span>{unreadNotifCount} new</span>
              </button>
            )}
            {backendOk !== null && (
              <span className={`neu-pill flex items-center gap-1 ${backendOk ? 'neu-pill--green' : 'neu-pill--red'}`}>
                <span className={`neu-dot ${backendOk ? '' : ''}`} style={{ backgroundColor: backendOk ? '#10b981' : '#ef4444' }} />
                {backendOk ? 'API Connected' : 'API Offline'}
              </span>
            )}
          </div>
        </div>
        {/* Tab bar */}
        <nav className="flex overflow-x-auto gap-1 px-2 pb-2">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`neu-nav-tab whitespace-nowrap px-3 py-2 text-sm ${
                activeTab === tab.id ? 'neu-nav-tab--active' : ''
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Page Content */}
      <main className="mx-auto max-w-7xl px-4 py-6">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'compliance' && <ComplianceTab />}
        {activeTab === 'audit' && <AuditLogTab />}
        {activeTab === 'content' && <ContentTab />}
        {activeTab === 'notifications' && <NotificationTab />}
        {activeTab === 'forecast' && <ForecastTab />}
        {activeTab === 'networks' && <NetworkTab />}
        {activeTab === 'social' && <SocialAccountTab />}
        {activeTab === 'queue' && <PostingQueueTab />}
        {activeTab === 'analytics' && <AccountAnalyticsTab />}
        {activeTab === 'system-logs' && <SystemLogsTab />}
        {activeTab === 'morphism' && <MorphismTab />}
      </main>

      {/* Footer */}
      <footer className="py-4 text-center text-xs text-slate-500">
        Affluence-AI v1.0 · Powered by FastAPI + React · Neumorphic UI
      </footer>
    </div>
  )
}

