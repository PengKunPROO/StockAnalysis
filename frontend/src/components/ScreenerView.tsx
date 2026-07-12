import { useEffect, useState, useCallback } from 'react'
import { useApp } from '../contexts/AppContext'
import { getScreenerFields, getScreenerSkills, runScreener } from '../api/screener'
import type { FilterField, ScreenerSkill, ScreenResult, FieldValue } from '../api/screener'

const SORT_OPTIONS = [
  { value: 'change_pct', label: '涨跌幅' },
  { value: 'amplitude', label: '振幅' },
  { value: 'roe', label: 'ROE' },
  { value: 'amount', label: '成交额' },
]

export default function ScreenerView() {
  const { dispatch } = useApp()
  const [fields, setFields] = useState<FilterField[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [skills, setSkills] = useState<ScreenerSkill[]>([])
  const [activeCat, setActiveCat] = useState('基本面')
  const [values, setValues] = useState<Record<string, FieldValue>>({})
  const [sort, setSort] = useState('change_pct')
  const [results, setResults] = useState<ScreenResult[]>([])
  const [count, setCount] = useState(0)
  const [warning, setWarning] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getScreenerFields().then(d => {
      setFields(d.fields)
      setCategories(d.categories)
      if (d.categories.length) setActiveCat(d.categories[0])
    }).catch(() => {})
    getScreenerSkills().then(d => setSkills(d.skills)).catch(() => {})
  }, [])

  const setField = (name: string, val: FieldValue) =>
    setValues(prev => ({ ...prev, [name]: val }))

  const applySkill = (s: ScreenerSkill) => {
    const next: Record<string, FieldValue> = {}
    for (const f of fields) {
      if (s.fields[f.name] !== undefined) next[f.name] = s.fields[f.name]
    }
    setValues(next)
  }

  const run = useCallback(async () => {
    setLoading(true); setWarning('')
    try {
      const r = await runScreener(values, sort, 50)
      setResults(r.results); setCount(r.count)
      if (r.warning) setWarning(r.warning)
    } catch (e: any) {
      setWarning(e.message || '筛选失败')
    } finally { setLoading(false) }
  }, [values, sort])

  const openStock = (r: ScreenResult) => {
    dispatch({ type: 'SET_STOCK', stock: { code: r.code, name: r.name, market: 'a_share', industry: '' } })
    dispatch({ type: 'SET_VIEW', view: 'stock' })
  }

  const catFields = fields.filter(f => f.category === activeCat)

  return (
    <div className="screener-view">
      {/* Filter section */}
      <div className="screener-filters">
        <div className="cat-tabs">
          {categories.map(c => (
            <button key={c} className={c === activeCat ? 'active' : ''} onClick={() => setActiveCat(c)}>{c}</button>
          ))}
        </div>

        <div className="field-grid">
          {catFields.map(f => (
            <FieldInput key={f.name} field={f} value={values[f.name]} onChange={v => setField(f.name, v)} />
          ))}
          {catFields.length === 0 && <span className="empty">无字段</span>}
        </div>

        <div className="filter-actions">
          <button className="run-btn" onClick={run} disabled={loading}>{loading ? '筛选中...' : '开始筛选'}</button>
          <span className="field-hint">字段由后端策略注册表动态提供</span>
        </div>
      </div>

      {/* Skills */}
      {skills.length > 0 && (
        <div className="skills-row">
          <span className="skills-label">选股 Skills:</span>
          {skills.map(s => (
            <button key={s.name} className="skill-chip" title={s.description} onClick={() => applySkill(s)}>{s.label}</button>
          ))}
        </div>
      )}

      {/* Results */}
      <div className="screener-results">
        <div className="results-header">
          <span className="count">结果: 共 {count} 只</span>
          <label className="sort-label">排序:
            <select value={sort} onChange={e => setSort(e.target.value)}>
              {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
        </div>

        {warning && <div className="results-warning">{warning}</div>}

        <table className="results-table">
          <thead>
            <tr>
              <th>代码</th><th>名称</th><th className="r">涨跌幅</th>
              <th className="r">ROE</th><th className="r">PE</th><th className="r">PB</th>
              <th>信号</th><th className="c"></th>
            </tr>
          </thead>
          <tbody>
            {results.map(r => {
              const up = (r.change_pct || 0) >= 0
              return (
                <tr key={r.code} onClick={() => openStock(r)}>
                  <td className="code">{r.code.split('.')[1]}</td>
                  <td className="name">{r.name}</td>
                  <td className="r" style={{ color: up ? 'var(--up)' : 'var(--down)' }}>
                    {(r.change_pct || 0) >= 0 ? '+' : ''}{(r.change_pct || 0).toFixed(2)}%
                  </td>
                  <td className="r accent">{r.roe != null ? `${r.roe.toFixed(1)}%` : '-'}</td>
                  <td className="r muted">{r.pe_ttm != null ? r.pe_ttm.toFixed(1) : '-'}</td>
                  <td className="r muted">{r.pb != null ? r.pb.toFixed(2) : '-'}</td>
                  <td>
                    {(r.signals || []).slice(0, 2).map((s, i) => (
                      <span key={i} className="sig-badge">{s}</span>
                    ))}
                    {(!r.signals || r.signals.length === 0) && <span className="muted2">-</span>}
                  </td>
                  <td className="c accent">→</td>
                </tr>
              )
            })}
            {results.length === 0 && !loading && (
              <tr><td colSpan={8} className="empty-row">设置筛选条件后点击"开始筛选"</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function FieldInput({ field, value, onChange }: {
  field: FilterField
  value: FieldValue | undefined
  onChange: (v: FieldValue) => void
}) {
  if (!field.available) {
    return (
      <label className="field field-unavailable">
        <span className="field-label">{field.label}</span>
        <span className="field-unavail">暂不可用</span>
      </label>
    )
  }
  if (field.type === 'boolean') {
    const checked = value === true
    return (
      <label className="field field-bool">
        <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
        <span className="field-label">{field.label}</span>
      </label>
    )
  }
  if (field.type === 'number_range') {
    const v = (value as { min?: number; max?: number } | undefined) || {}
    const set = (k: 'min' | 'max', val: string) => {
      const num = val === '' ? undefined : Number(val)
      onChange({ ...v, [k]: num })
    }
    return (
      <label className="field">
        <span className="field-label">{field.label}{field.unit && `(${field.unit})`}</span>
        <span className="range-inputs">
          <input type="number" placeholder="min" value={v.min ?? ''} onChange={e => set('min', e.target.value)} />
          <span className="dash">~</span>
          <input type="number" placeholder="max" value={v.max ?? ''} onChange={e => set('max', e.target.value)} />
        </span>
      </label>
    )
  }
  return null
}
