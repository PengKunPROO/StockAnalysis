import React, { createContext, useContext, useReducer, useEffect } from 'react'
import type { StockInfo, SkillMeta, DiagnosisSession, WatchlistItem, SignalsPayload } from '../types'

const STORAGE_KEY = 'stockagent_state'

export type AppView = 'stock' | 'screener' | 'intel'

interface AppState {
  currentStock: StockInfo | null
  skills: SkillMeta[]
  sessions: DiagnosisSession[]
  watchlist: WatchlistItem[]
  skillManagerOpen: boolean
  activeView: AppView
  signals: SignalsPayload | null
}

function loadState(): Partial<AppState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return {}
}

function saveState(state: AppState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      currentStock: state.currentStock,
      watchlist: state.watchlist,
    }))
  } catch {}
}

const initialState: AppState = {
  currentStock: loadState().currentStock || null,
  skills: [],
  sessions: [],
  watchlist: loadState().watchlist || [],
  skillManagerOpen: false,
  activeView: 'stock',
  signals: null,
}

type Action =
  | { type: 'SET_STOCK'; stock: StockInfo }
  | { type: 'SET_SKILLS'; skills: SkillMeta[] }
  | { type: 'SET_SESSIONS'; sessions: DiagnosisSession[] }
  | { type: 'SET_WATCHLIST'; watchlist: WatchlistItem[] }
  | { type: 'TOGGLE_SKILL_MANAGER'; open?: boolean }
  | { type: 'SET_VIEW'; view: AppView }
  | { type: 'SET_SIGNALS'; signals: SignalsPayload | null }

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_STOCK': return { ...state, currentStock: action.stock, signals: null }
    case 'SET_SKILLS': return { ...state, skills: action.skills }
    case 'SET_SESSIONS': return { ...state, sessions: action.sessions }
    case 'SET_WATCHLIST': return { ...state, watchlist: action.watchlist }
    case 'TOGGLE_SKILL_MANAGER': return { ...state, skillManagerOpen: action.open ?? !state.skillManagerOpen }
    case 'SET_VIEW': return { ...state, activeView: action.view }
    case 'SET_SIGNALS': return { ...state, signals: action.signals }
    default: return state
  }
}

const AppCtx = createContext<{ state: AppState; dispatch: React.Dispatch<Action> } | null>(null)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  // Persist on changes
  useEffect(() => { saveState(state) }, [state.currentStock, state.watchlist])

  return <AppCtx.Provider value={{ state, dispatch }}>{children}</AppCtx.Provider>
}

export function useApp() {
  const ctx = useContext(AppCtx)
  if (!ctx) throw new Error('useApp must be inside AppProvider')
  return ctx
}
