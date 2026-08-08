import { useState, useEffect, useCallback } from 'react'

// In production (single-service deploy), the API is served from the same origin.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.PROD ? '' : 'http://localhost:8000')
const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN ?? 'admin-token'
const VIEWER_TOKEN = import.meta.env.VITE_VIEWER_TOKEN ?? 'viewer-token'

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

const SAMPLE_FEED = [
  { title: 'Noise-Cancelling Headphones', networkName: 'Amazon', price: 199.99, commissionRate: 0.06, cat: 'Audio', description: 'Studio-grade ANC headphones.' },
  { name: 'Yoga Master Course', network: 'clickbank', amount: 79, rate: 0.5, category: 'Fitness' },
  { productName: 'VPN Pro 2025', provider: 'CJ', sale_price: 59.99, commissionRate: 0.3 },
  { productId: 'JM-XYZ', name: 'Robot Vacuum', networkName: 'Jumia', price: 149, commissionRate: 0.1, category: 'Home' },
]

function StatusDot({ on, color = '#10b981' }) {
  return <span className="neu-dot" style={{ backgroundColor: on ? color : '#c3cbd8' }} />
}

function Badge({ children, color = 'slate' }) {
  return <span className={`neu-pill neu-pill--${color}`}>{children}</span>
}

export default function MorphismTab() {
  const [feedResult, setFeedResult] = useState(null)
  const [feedLoading, setFeedLoading] = useState(false)
  const [workflowMap, setWorkflowMap] = useState(null)
  const [routeResult, setRouteResult] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)
  const [links, setLinks] = useState([])
  const [products, setProducts] = useState([])
  const [selectedLink, setSelectedLink] = useState('')
  const [contentResult, setContentResult] = useState(null)
  const [contentLoading, setContentLoading] = useState(false)
  const [status, setStatus] = useState('')

  const loadBase = useCallback(async () => {
    try {
      const [rm, an] = await Promise.all([
        api('/morph/workflow', { viewer: true }),
        api('/morph/analytics', { viewer: true }),
      ])
      setWorkflowMap(rm)
      setAnalytics(an)
    } catch (e) { setStatus(e.message) }
  }, [])

  useEffect(() => { loadBase() }, [loadBase])

  const handleFeed = async () => {
    setFeedLoading(true)
    try {
      const r = await api('/morph/feed', { method: 'POST', body: { items: SAMPLE_FEED } })
      setFeedResult(r)
      setStatus(`Data morphism: ${r.morphed_count} items standardized`)
    } catch (e) { setStatus(e.message) }
    finally { setFeedLoading(false) }
  }

  const handleLoadLinks = async () => {
    try {
      const r = await api('/report', { viewer: true }).catch(() => null)
      // Load products from scan to find links
      const scan = await api('/scan', { method: 'POST' }).catch(() => null)
      if (scan && scan.products) {
        setProducts(scan.products)
      }
      // Load existing links via analytics overview / top-links
      const top = await api('/analytics/top-links?limit=20', { viewer: true }).catch(() => [])
      if (Array.isArray(top) && top.length) {
        setLinks(top)
        setSelectedLink(String(top[0].link_id))
      }
      if (r) setStatus('Links loaded')
    } catch (e) { setStatus(e.message) }
  }

  const handleContentMorph = async () => {
    if (!selectedLink) return
    setContentLoading(true)
    try {
      const r = await api('/morph/content', { method: 'POST', body: { link_id: Number(selectedLink), category: 'default' } })
      setContentResult(r)
      setStatus(`Content morphism: ${r.format_count} formats generated`)
    } catch (e) { setStatus(e.message) }
    finally { setContentLoading(false) }
  }

  const handleRoute = async (action, validated) => {
    try {
      const r = await api('/morph/workflow/route', { method: 'POST', body: { action, validated } })
      setRouteResult(r)
      setStatus(`Workflow morphism: '${action}' -> ${r.execution_path} (${r.status})`)
    } catch (e) { setStatus(e.message) }
  }

  const refreshAnalytics = async () => {
    setAnalyticsLoading(true)
    try {
      const an = await api('/morph/analytics', { viewer: true })
      setAnalytics(an)
      setStatus('Analytics morphism refreshed')
    } catch (e) { setStatus(e.message) }
    finally { setAnalyticsLoading(false) }
  }

  const perfBadge = (p) => ({
    high_performing: ['green', 'High performing'],
    promising: ['sky', 'Promising'],
    moderate: ['amber', 'Moderate'],
    needs_attention: ['red', 'Needs attention'],
  })[p] || ['slate', p]

  return (
    <div className="space-y-6">
      {/* Status bar */}
      <div className="neu-inset px-4 py-3">
        <p className="text-sm text-slate-700">{status || 'Morphism Layer Engine — semantic data transformation pipeline'}</p>
      </div>

      {/* 4 engine overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ['📥 Data', 'Raw feed → standardized product objects'],
          ['✍️ Content', 'Validated links → blog/tweet/newsletter'],
          ['🛤️ Workflow', 'Actions → auto-post or manual-approval'],
          ['📈 Analytics', 'Raw clicks → CTR, ROI, trending products'],
        ].map(([t, d]) => (
          <div key={t} className="neu-card neu-card--hover p-4">
            <div className="text-2xl">{t.split(' ')[0]}</div>
            <div className="mt-1 font-semibold text-slate-800">{t.split(' ')[1]} Morphism</div>
            <p className="mt-1 text-xs text-slate-500">{d}</p>
          </div>
        ))}
      </div>

      {/* ── Data Morphism ── */}
      <div className="neu-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">1 · Data Morphism <span className="text-sm font-normal text-slate-400">(raw feed → standardized)</span></h2>
          <button className="neu-btn neu-btn--accent px-3 py-1.5 text-sm" onClick={handleFeed} disabled={feedLoading}>
            {feedLoading ? 'Morphing…' : '▶ Morph sample feed'}
          </button>
        </div>

        {/* Raw input */}
        <div className="neu-inset-soft mb-3 p-3">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Raw feed (loose schemas)</p>
          <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-xs text-slate-600">{JSON.stringify(SAMPLE_FEED, null, 2)}</pre>
        </div>

        {feedResult && (
          <div className="neu-inset-soft p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Standardized output · {feedResult.morphed_count}/{feedResult.source_count} morphed
            </p>
            <div className="max-h-64 overflow-auto space-y-2">
              {feedResult.products.map((p, i) => (
                <div key={i} className="flex items-start justify-between rounded-lg bg-white/50 px-3 py-2 text-sm">
                  <div>
                    <span className="font-medium text-slate-800">{p.name}</span>
                    <div className="text-xs text-slate-500">{p.network_label} · {p.category} · slug: <code>{p.slug}</code></div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-slate-800">${p.price.toFixed(2)}</div>
                    <div className="text-xs text-slate-500">{p.commission_pct}% → est ${p.estimated_commission.toFixed(2)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Content Morphism ── */}
      <div className="neu-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">2 · Content Morphism <span className="text-sm font-normal text-slate-400">(validated link → multi-format)</span></h2>
          <div className="flex gap-2">
            <button className="neu-btn neu-btn--flat px-3 py-1.5 text-sm text-slate-600" onClick={handleLoadLinks}>Load links</button>
            <button className="neu-btn neu-btn--accent px-3 py-1.5 text-sm" onClick={handleContentMorph} disabled={contentLoading || !selectedLink}>
              {contentLoading ? 'Generating…' : '⚡ Transform'}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select className="neu-input px-3 py-2 text-sm flex-1 min-w-[220px]" value={selectedLink} onChange={e => setSelectedLink(e.target.value)}>
            <option value="">Select an affiliate link…</option>
            {links.map(l => (
              <option key={l.link_id} value={l.link_id}>
                {l.product_name || l.tracking_code} — {l.clicks} clicks / {l.conversions} conv
              </option>
            ))}
          </select>
          {products.length > 0 && (
            <span className="text-xs text-slate-500">{products.length} products scanned available</span>
          )}
        </div>

        {contentResult && (
          <div className="mt-3 grid gap-3 lg:grid-cols-3">
            {Object.entries(contentResult.formats).map(([key, fmt]) => (
              <div key={key} className="neu-inset-soft p-3">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{key}</span>
                  <Badge color={key === 'blog' ? 'indigo' : key === 'social' ? 'sky' : 'green'}>{fmt.platform}</Badge>
                </div>
                <p className="mb-2 text-sm font-medium text-slate-700">{fmt.title || fmt.platform}</p>
                <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-xs text-slate-600">{fmt.content}</pre>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Workflow Morphism ── */}
      <div className="neu-card p-4">
        <h2 className="mb-3 text-lg font-semibold text-slate-800">3 · Workflow Morphism <span className="text-sm font-normal text-slate-400">(validated actions → execution paths)</span></h2>

        {workflowMap && (
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="neu-inset-soft p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Global mode</p>
              <div className="flex items-center gap-3">
                <Badge color={workflowMap.posting_mode === 'auto' ? 'green' : 'blue'}>
                  {workflowMap.posting_mode === 'auto' ? '⚡ AUTO-POST' : '👤 MANUAL APPROVAL'}
                </Badge>
                <span className="text-sm text-slate-600">Primary path: <strong>{workflowMap.primary_execution_path}</strong></span>
              </div>
              <div className="mt-3 space-y-1.5 text-sm">
                {Object.entries(workflowMap.routing || {})
                  .filter(([k]) => !['distribution'].includes(k))
                  .map(([step, cfg]) => (
                    <div key={step} className="flex items-center justify-between text-xs">
                      <span className="font-mono text-slate-600">{step}</span>
                      <span className="flex items-center gap-1 text-slate-500">
                        {cfg.gated ? '🔒 gated' : '↦'} {cfg.next}
                      </span>
                    </div>
                  ))}
              </div>
            </div>

            <div className="neu-inset-soft p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Route an action</p>
              <div className="flex flex-wrap gap-2">
                {[['post_content', true], ['post_content', false], ['scan', true], ['generate_content', true]].map(([action, v]) => (
                  <button key={`${action}-${v}`} className="neu-btn px-3 py-1.5 text-xs" onClick={() => handleRoute(action, v)}>
                    {action}{v ? ' ✓' : ' ✗'}
                  </button>
                ))}
              </div>
              {routeResult && (
                <div className="mt-3 rounded-lg bg-white/60 p-3">
                  <div className="flex items-center gap-2 text-sm">
                    <StatusDot on={routeResult.status !== 'blocked'} color={routeResult.status === 'blocked' ? '#ef4444' : '#10b981'} />
                    <code className="text-xs text-slate-600">{routeResult.action}</code>
                    <Badge color={routeResult.status === 'blocked' ? 'red' : routeResult.status === 'queued' ? 'yellow' : 'green'}>{routeResult.status}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">Path: <code className="text-slate-700">{routeResult.execution_path}</code> · {routeResult.detail}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Distribution path map */}
        {workflowMap?.routing?.distribution && (
          <div className="mt-3 neu-inset-soft p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Distribution execution</p>
            {Object.entries(workflowMap.routing.distribution).map(([path, cfg]) => (
              <div key={path} className="flex items-start gap-2 text-sm">
                <StatusDot on color="#6366f1" />
                <div>
                  <code className="font-semibold text-slate-700">{path}</code>
                  <p className="text-xs text-slate-500">{cfg.description}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Analytics Morphism ── */}
      <div className="neu-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">4 · Analytics Morphism <span className="text-sm font-normal text-slate-400">(raw data → actionable insights)</span></h2>
          <button className="neu-btn neu-btn--flat px-3 py-1.5 text-sm text-slate-600" onClick={refreshAnalytics} disabled={analyticsLoading}>
            {analyticsLoading ? 'Refreshing…' : '↻ Refresh'}
          </button>
        </div>

        {analytics?.summary && (
          <>
            {/* Summary cards */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ['Total Clicks', analytics.summary.total_clicks, 'sky'],
                ['Conversions', analytics.summary.total_conversions, 'indigo'],
                ['Conversion Rate', `${analytics.summary.overall_conversion_rate}%`, 'green'],
                ['Est. Earnings / ROI', `$${analytics.summary.total_earnings}`, 'amber'],
              ].map(([t, v, c]) => (
                <div key={t} className="neu-inset-soft p-3 text-center">
                  <div className="text-2xl font-bold text-slate-800">{v}</div>
                  <div className="text-xs text-slate-500 mt-1">{t}</div>
                </div>
              ))}
            </div>

            {/* Trending products */}
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Trending products</p>
                <div className="neu-inset-soft p-2 space-y-1.5">
                  {analytics.trending_products.length === 0 && <p className="text-xs text-slate-400">No data yet.</p>}
                  {analytics.trending_products.map((t, i) => {
                    const [pcolor, plabel] = perfBadge(t.performance)
                    return (
                      <div key={i} className="flex items-center justify-between rounded-lg bg-white/50 px-3 py-2 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-700">#{i + 1}</span>
                          <div>
                            <span className="font-medium text-slate-800">{t.product_name}</span>
                            <div className="text-xs text-slate-500">{t.network} · {t.clicks} clicks → {t.conversions} conv</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge color={pcolor}>{plabel}</Badge>
                          <div className="text-xs text-slate-500 mt-0.5">${t.earnings}</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Per-link insights</p>
                <div className="neu-inset-soft max-h-64 overflow-auto p-2 space-y-1.5">
                  {analytics.insights.length === 0 && <p className="text-xs text-slate-400">No links yet.</p>}
                  {analytics.insights.map((ins, i) => {
                    const [pcolor, plabel] = perfBadge(ins.performance)
                    return (
                      <div key={i} className="flex items-center justify-between rounded-lg bg-white/50 px-3 py-2 text-xs">
                        <span className="truncate text-slate-700">{ins.product_name || `Link #${ins.link_id}`}</span>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-slate-500">{ins.conversion_rate}%</span>
                          <Badge color={pcolor}>{plabel}</Badge>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </>
        )}

        {!analytics && <p className="text-sm text-slate-400">Loading analytics morphism…</p>}
      </div>
    </div>
  )
}
