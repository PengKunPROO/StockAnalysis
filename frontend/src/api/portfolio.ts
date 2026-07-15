// frontend/src/api/portfolio.ts

export interface Holding {
  id: number; code: string; name: string;
  shares: number; avg_cost: number; buy_date: string | null;
  status: string; updated_at: string;
}

export interface Transaction {
  id: number; code: string; name: string;
  action: 'buy' | 'sell'; shares: number; price: number;
  amount: number; traded_at: string; note: string | null;
}

export interface ReportSummary {
  id: string; report_date: string; status: string;
  total_market_value: number | null; total_pnl: number | null;
  pnl_pct: number | null; summary: string;
}

export interface ReportSectionRaw {
  section_type: string; stock_code: string | null;
  content: string; status: string;
}

export interface ReportContextRaw {
  id: number; stock_code: string;
  advice_type: string; advice_text: string | null;
  key_price: number | null;
  executed: boolean; execution_result: string | null;
}

export interface ReportDetail {
  id: string; report_date: string; status: string;
  total_market_value: number | null;
  total_cost: number | null;
  total_pnl: number | null;
  pnl_pct: number | null;
  summary: string | null;
  sections: ReportSectionRaw[];
  contexts: ReportContextRaw[];
}

const BASE = '/api/v1/portfolio'

export async function getHoldings(): Promise<{ holdings: Holding[] }> {
  const r = await fetch(`${BASE}/holdings`)
  if (!r.ok) throw new Error(`获取持仓失败: ${r.status}`)
  return r.json()
}

export async function createHolding(data: {
  code: string; name: string; shares: number;
  avg_cost: number; buy_date: string;
}): Promise<Holding> {
  const r = await fetch(`${BASE}/holdings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return r.json()
}

export async function deleteHolding(id: number): Promise<void> {
  const r = await fetch(`${BASE}/holdings/${id}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(`删除持仓失败: ${r.status}`)
}

export async function getHoldingsRealtime(): Promise<{
  prices: Record<string, { price: number; change_pct: number }>
  errors: Array<{ code: string; error: string }> | null
}> {
  const r = await fetch(`${BASE}/holdings/realtime`)
  if (!r.ok) throw new Error(`获取实时行情失败: ${r.status}`)
  return r.json()
}

export async function stockLookup(q: string): Promise<{
  results: Array<{ code: string; name: string; market: string }>
}> {
  const r = await fetch(`${BASE}/stock-lookup?q=${encodeURIComponent(q)}`)
  return r.json()
}

export async function getTransactions(
  page = 1, limit = 20, code = ''
): Promise<{ transactions: Transaction[]; total: number; page: number; total_pages: number }> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (code) params.set('code', code)
  const r = await fetch(`${BASE}/transactions?${params}`)
  return r.json()
}

export async function createTransaction(data: {
  code: string; name: string; action: 'buy' | 'sell';
  shares: number; price: number; traded_at: string; note?: string;
}): Promise<Transaction> {
  const r = await fetch(`${BASE}/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error(`创建交易失败: ${r.status}`)
  return r.json()
}

export async function deleteTransaction(id: number): Promise<void> {
  await fetch(`${BASE}/transactions/${id}`, { method: 'DELETE' })
}

export async function getReports(limit = 30): Promise<{ reports: ReportSummary[] }> {
  const r = await fetch(`${BASE}/reports?limit=${limit}`)
  return r.json()
}

export async function getReport(date: string): Promise<ReportDetail | null> {
  const r = await fetch(`${BASE}/reports/${date}`)
  if (!r.ok) return null
  return r.json()
}

export async function getTodayReport(): Promise<ReportDetail | null> {
  const r = await fetch(`${BASE}/reports/today`)
  if (!r.ok) return null
  return r.json()
}

export async function generateReport(): Promise<{ report_id?: string; status: string }> {
  const r = await fetch(`${BASE}/reports/generate`, { method: 'POST' })
  return r.json()
}
