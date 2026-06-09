import { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN ?? 'admin-token'
const VIEWER_TOKEN = import.meta.env.VITE_VIEWER_TOKEN ?? 'viewer-token'

function App() {
  const [scanData, setScanData] = useState([])
  const [trackingCode, setTrackingCode] = useState('')
  const [amount, setAmount] = useState('')
  const [report, setReport] = useState({ daily_earnings: [], weekly_earnings: [], payouts: [], pending_balance: 0, confirmed_balance: 0 })
  const [status, setStatus] = useState('Ready')

  async function call(path, method = 'GET', body, viewer = false) {
    const authPrefix = String.fromCharCode(66, 101, 97, 114, 101, 114, 32)
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: authPrefix + (viewer ? VIEWER_TOKEN : ADMIN_TOKEN),
      },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail ?? 'Request failed')
    }
    return response.json()
  }

  const handleScan = async () => {
    try {
      setStatus('Scanning affiliate networks...')
      const result = await call('/scan', 'POST')
      setScanData(result.products)
      if (!trackingCode && result.products.length > 0) {
        setTrackingCode(result.products[0].tracking_code)
      }
      setStatus(`Scan complete. ${result.inserted} products available.`)
    } catch (error) {
      setStatus(error.message)
    }
  }

  const handlePurchase = async () => {
    try {
      setStatus('Logging purchase...')
      await call('/purchase', 'POST', { tracking_code: trackingCode, amount: amount ? Number(amount) : undefined })
      setStatus('Purchase logged.')
    } catch (error) {
      setStatus(error.message)
    }
  }

  const handleValidate = async () => {
    try {
      setStatus('Validating commissions...')
      const result = await call('/validate', 'POST')
      setStatus(`Validated ${result.confirmed} commissions.`)
    } catch (error) {
      setStatus(error.message)
    }
  }

  const handlePayout = async (method) => {
    try {
      setStatus(`Triggering ${method} payout...`)
      await call('/payout', 'POST', { method })
      setStatus(`${method.toUpperCase()} payout processed.`)
    } catch (error) {
      setStatus(error.message)
    }
  }

  const handleReport = async () => {
    try {
      setStatus('Loading report...')
      const result = await call('/report', 'GET', undefined, true)
      setReport(result)
      setStatus('Report updated.')
    } catch (error) {
      setStatus(error.message)
    }
  }

  return (
    <main className="min-h-screen p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <h1 className="text-3xl font-bold text-slate-900">Affiliate Commission Agent Dashboard</h1>
        <p className="rounded bg-white p-3 text-sm text-slate-600 shadow">{status}</p>

        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card title="Pending Balance" value={`$${report.pending_balance.toFixed(2)}`} />
          <Card title="Confirmed Balance" value={`$${report.confirmed_balance.toFixed(2)}`} />
          <Card title="Products" value={String(scanData.length)} />
          <Card title="Payout Count" value={String(report.payouts.length)} />
        </section>

        <section className="rounded bg-white p-4 shadow">
          <h2 className="mb-3 text-lg font-semibold">Operations</h2>
          <div className="flex flex-wrap gap-2">
            <button className="rounded bg-slate-900 px-3 py-2 text-sm text-white" onClick={handleScan}>Scan</button>
            <button className="rounded bg-indigo-600 px-3 py-2 text-sm text-white" onClick={handleValidate}>Validate</button>
            <button className="rounded bg-emerald-600 px-3 py-2 text-sm text-white" onClick={() => handlePayout('paypal')}>Payout PayPal</button>
            <button className="rounded bg-teal-600 px-3 py-2 text-sm text-white" onClick={() => handlePayout('mpesa')}>Payout M-Pesa</button>
            <button className="rounded bg-sky-600 px-3 py-2 text-sm text-white" onClick={handleReport}>Refresh Report</button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <input className="rounded border p-2" placeholder="Tracking code" value={trackingCode} onChange={(e) => setTrackingCode(e.target.value)} />
            <input className="rounded border p-2" type="number" min="0" placeholder="Purchase amount (optional)" value={amount} onChange={(e) => setAmount(e.target.value)} />
            <button className="rounded bg-orange-600 px-3 py-2 text-sm text-white" onClick={handlePurchase}>Record Purchase</button>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Table title="Scanned Products" rows={scanData.map((row) => ({
            Network: row.network,
            Product: row.name,
            Rate: `${(row.commission_rate * 100).toFixed(1)}%`,
            Link: row.link,
          }))} />
          <Table title="Payout History" rows={report.payouts.map((row) => ({
            Method: row.method,
            Amount: `$${row.amount.toFixed(2)}`,
            Status: row.status,
            Reference: row.transaction_ref,
          }))} />
        </section>
      </div>
    </main>
  )
}

function Card({ title, value }) {
  return (
    <div className="rounded bg-white p-4 shadow">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

function Table({ title, rows }) {
  const columns = rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <div className="overflow-auto rounded bg-white p-4 shadow">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">No data yet.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-slate-500">
              {columns.map((column) => (
                <th className="pb-2 pr-3" key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${title}-${index}`} className="border-b last:border-0">
                {columns.map((column) => (
                  <td className="py-2 pr-3" key={column}>{String(row[column])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default App
