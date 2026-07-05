import { useState, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { getRealtime, getFinancial, getIndicators } from '../api/stocks'

export default function InfoCards() {
  const { state } = useApp()
  const [realtime, setRealtime] = useState<any>(null)
  const [financial, setFinancial] = useState<any>(null)
  const [indicators, setIndicators] = useState<any>(null)

  useEffect(() => {
    if (!state.currentStock) return
    const code = state.currentStock.code
    Promise.all([
      getRealtime(code), getFinancial(code), getIndicators(code, 60)
    ]).then(([r, f, i]) => { setRealtime(r); setFinancial(f); setIndicators(i) })
  }, [state.currentStock])

  if (!realtime && !financial && !indicators) return null

  const macd = indicators?.data?.[indicators.data.length - 1]?.macd
  const rsi = indicators?.data?.[indicators.data.length - 1]?.rsi

  return (
    <div className="stats">
      <div className="cell"><div className="l">最新</div><div className="v" style={{color: realtime?.change_pct>0?'var(--up)':realtime?.change_pct<0?'var(--down)':'var(--h)'}}>¥{realtime?.price?.toFixed(2)||'--'}</div></div>
      <div className="cell"><div className="l">涨跌</div><div className="v" style={{color: realtime?.change_pct>0?'var(--up)':realtime?.change_pct<0?'var(--down)':'var(--h)'}}>{realtime?.change_pct!=null?(realtime.change_pct>0?'+':'')+realtime.change_pct.toFixed(2)+'%':'--'}</div></div>
      <div className="cell"><div className="l">最高</div><div className="v">¥{realtime?.high?.toFixed(2)||'--'}</div></div>
      <div className="cell"><div className="l">最低</div><div className="v">¥{realtime?.low?.toFixed(2)||'--'}</div></div>
      <div className="cell"><div className="l">成交</div><div className="v">{realtime?.volume?((realtime.volume/10000).toFixed(0)+'万'):'--'}</div></div>
      <div className="cell"><div className="l">ROE</div><div className="v">{financial?.roe!=null?(financial.roe*100).toFixed(1)+'%':'--'}</div></div>
      <div className="cell"><div className="l">负债率</div><div className="v">{financial?.debt_ratio!=null?(financial.debt_ratio*100).toFixed(1)+'%':'--'}</div></div>
      <div className="cell"><div className="l">MACD</div><div className="v" style={{color:macd?.macd>0?'var(--up)':'var(--down)'}}>{macd?.macd!=null?macd.macd.toFixed(2):'--'}</div></div>
      <div className="cell"><div className="l">RSI</div><div className="v">{rsi?.toFixed?rsi.toFixed(1):'--'}</div></div>
    </div>
  )
}
