import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ForceGraph2D from 'react-force-graph-2d'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import { forceCollide } from 'd3-force-3d'
import { fetchHistory, type WeeklyHistoryItem } from '../api/history'
import { TIPS } from '../constants/tooltips'

// ── 타입 ─────────────────────────────────────────────────────────────────────

interface GNode {
  id: string
  weight: number
  lastUsed: string  // ISO date of most recent appearance
}

interface GLink {
  source: string
  target: string
  weight: number
}

type ResolvedLink = Omit<GLink, 'source' | 'target'> & {
  source: GNode | string
  target: GNode | string
}

function linkId(link: ResolvedLink): [string, string] {
  const s = typeof link.source === 'object' ? link.source.id : link.source
  const t = typeof link.target === 'object' ? link.target.id : link.target
  return [s, t]
}

// ── 색상 스케일 (저빈도 → 고빈도) ────────────────────────────────────────────

// blue-300 → indigo-500 → violet-700
const COLOR_STOPS = [
  [147, 197, 253],
  [99,  102, 241],
  [109,  40, 217],
] as const

function lerpColor(t: number): string {
  t = Math.max(0, Math.min(1, t))
  let from, to, s
  if (t <= 0.5) {
    from = COLOR_STOPS[0]; to = COLOR_STOPS[1]; s = t * 2
  } else {
    from = COLOR_STOPS[1]; to = COLOR_STOPS[2]; s = (t - 0.5) * 2
  }
  const r = Math.round(from[0] + (to[0] - from[0]) * s)
  const g = Math.round(from[1] + (to[1] - from[1]) * s)
  const b = Math.round(from[2] + (to[2] - from[2]) * s)
  return `rgb(${r},${g},${b})`
}

// ── 그래프 데이터 빌드 ────────────────────────────────────────────────────────

function buildGraph(history: WeeklyHistoryItem[], minEdge: number) {
  const nodeW = new Map<string, number>()
  const edgeW = new Map<string, number>()
  const lastUsed = new Map<string, string>()  // title → latest week_end_date

  for (const week of history) {
    const titles = week.sequence_entries.map(e => e.title)
    for (const t of titles) {
      nodeW.set(t, (nodeW.get(t) ?? 0) + 1)
      const prev = lastUsed.get(t)
      if (!prev || week.week_end_date > prev) lastUsed.set(t, week.week_end_date)
    }
    for (let i = 0; i < titles.length; i++) {
      for (let j = i + 1; j < titles.length; j++) {
        const key = [titles[i], titles[j]].sort().join('\x00')
        edgeW.set(key, (edgeW.get(key) ?? 0) + 1)
      }
    }
  }

  const links: GLink[] = []
  const connected = new Set<string>()
  for (const [key, w] of edgeW) {
    if (w < minEdge) continue
    const [a, b] = key.split('\x00')
    links.push({ source: a, target: b, weight: w })
    connected.add(a); connected.add(b)
  }

  const nodes: GNode[] = Array.from(connected).map(id => ({
    id,
    weight: nodeW.get(id) ?? 0,
    lastUsed: lastUsed.get(id) ?? '',
  }))
  return { nodes, links }
}

function daysSince(dateStr: string): number {
  if (!dateStr) return -1
  const [y, m, d] = dateStr.split('-').map(Number)
  const last = new Date(y, m - 1, d)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return Math.floor((today.getTime() - last.getTime()) / 86400000)
}

// ── 캔버스 컴포넌트 ───────────────────────────────────────────────────────────

function GraphCanvas({ nodes, links }: { nodes: GNode[]; links: GLink[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null)
  const fitDone = useRef(false)

  const [dim, setDim] = useState({ w: 800, h: 500 })
  const [hovered, setHovered] = useState<GNode | null>(null)
  const [selected, setSelected] = useState<GNode | null>(null)

  // 렌더마다 새 객체가 생기면 ForceGraph가 데이터 변경으로 인식해 시뮬을 리셋함
  const graphData = useMemo(() => ({ nodes, links }), [nodes, links])

  // 컨테이너 크기 추적
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      setDim({ w: entry.contentRect.width, h: Math.max(400, entry.contentRect.height) })
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // 데이터 바뀔 때마다: 링크 거리 적용 + 충돌 방지 + 재시뮬
  useEffect(() => {
    const g = graphRef.current
    if (!g) return
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    g.d3Force('link')?.distance((link: any) => {
      const sw = typeof link.source === 'object' ? (link.source as GNode).weight : 0
      const tw = typeof link.target === 'object' ? (link.target as GNode).weight : 0
      return (nodeR(sw) + nodeR(tw)) * 3
    })
    // 한국어 글자 너비 ≈ 8px at 8px font → 절반 + 여백
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    g.d3Force('collision', forceCollide((node: any) => {
      const n = node as GNode
      const labelHalfW = Math.min(n.id.length, 15) * 8 / 2
      return Math.max(nodeR(n.weight) + 8, labelHalfW + 6)
    }))
    g.d3Force('charge')?.strength(-200)
    fitDone.current = false
    g.d3ReheatSimulation()
  }, [nodes, links])

  // min/max 기반 동적 색상 스케일
  const { minW, maxW } = useMemo(() => {
    if (!nodes.length) return { minW: 0, maxW: 1 }
    let min = Infinity, max = -Infinity
    for (const n of nodes) {
      if (n.weight < min) min = n.weight
      if (n.weight > max) max = n.weight
    }
    return { minW: min, maxW: max }
  }, [nodes])

  function nodeBaseColor(weight: number): string {
    if (maxW === minW) return lerpColor(0.5)
    return lerpColor((weight - minW) / (maxW - minW))
  }

  // 선택된 노드의 이웃 집합
  const neighborIds = useMemo<Set<string> | null>(() => {
    if (!selected) return null
    const ids = new Set<string>([selected.id])
    for (const l of links) {
      if (l.source === selected.id) ids.add(l.target as string)
      if (l.target === selected.id) ids.add(l.source as string)
    }
    return ids
  }, [selected, links])

  function nodeR(weight: number) {
    return Math.max(10, Math.min(28, 10 + weight * 2.5))
  }

  // 노드 커스텀 페인트 (원만, 라벨은 onRenderFramePost에서 최상단 렌더)
  function paintNode(raw: object, ctx: CanvasRenderingContext2D) {
    const node = raw as GNode & { x: number; y: number }
    const r = nodeR(node.weight)
    const dimmed = neighborIds !== null && !neighborIds.has(node.id)
    const isSel = selected?.id === node.id
    const isHov = hovered?.id === node.id

    ctx.beginPath()
    ctx.arc(node.x, node.y, r + (isSel || isHov ? 2 : 0), 0, Math.PI * 2)
    ctx.fillStyle = dimmed
      ? 'rgba(200,200,215,0.3)'
      : isSel  ? '#4f46e5'
      : isHov  ? '#818cf8'
      : nodeBaseColor(node.weight)
    ctx.fill()

    if (isSel || isHov) {
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()
    }
  }

  function paintPointer(raw: object, color: string, ctx: CanvasRenderingContext2D) {
    const node = raw as GNode & { x: number; y: number }
    const r = nodeR(node.weight) + 10
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
    ctx.fill()
  }

  const selectedLinks = selected
    ? links
        .filter(l => l.source === selected.id || l.target === selected.id)
        .sort((a, b) => b.weight - a.weight)
        .slice(0, 6)
    : []

  return (
    <div ref={containerRef} className="relative flex-1 min-h-0 overflow-hidden">
      <ForceGraph2D
        ref={graphRef}
        width={dim.w}
        height={dim.h}
        graphData={graphData}
        nodeId="id"
        nodeCanvasObject={paintNode}
        nodeCanvasObjectMode={() => 'replace'}
        nodePointerAreaPaint={paintPointer}
        linkWidth={(l) => Math.min(6, 0.7 + (l as GLink).weight * 0.9)}
        linkColor={(l) => {
          const link = l as ResolvedLink
          const [s, t] = linkId(link)
          const w = link.weight
          if (!neighborIds) return `rgba(99,102,241,${Math.min(0.8, 0.1 + w * 0.2)})`
          return neighborIds.has(s) && neighborIds.has(t)
            ? `rgba(99,102,241,${Math.min(0.9, 0.2 + w * 0.3)})`
            : 'rgba(200,200,220,0.08)'
        }}
        linkDirectionalArrowLength={0}
        onNodeHover={(node) => setHovered(node as GNode | null)}
        onNodeClick={(node) => {
          const n = node as GNode
          setSelected(prev => prev?.id === n.id ? null : n)
        }}
        onBackgroundClick={() => setSelected(null)}
        onEngineStop={() => {
          if (!fitDone.current) {
            fitDone.current = true
            graphRef.current?.zoomToFit(400, 80)
          }
        }}
        warmupTicks={80}
        cooldownTicks={80}
        d3VelocityDecay={0.25}
        backgroundColor="#ffffff"
        onRenderFramePost={(ctx) => {
          for (const node of nodes) {
            const n = node as GNode & { x?: number; y?: number }
            if (n.x == null) continue
            const r = nodeR(n.weight)
            const dimmed = neighborIds !== null && !neighborIds.has(n.id)
            const isSel = selected?.id === n.id
            const isHov = hovered?.id === n.id
            ctx.font = `${isSel || isHov ? 'bold ' : ''}8px sans-serif`
            ctx.fillStyle = dimmed ? 'rgba(180,180,200,0.4)' : '#374151'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'top'
            const label = n.id.length > 15 ? n.id.slice(0, 14) + '…' : n.id
            ctx.fillText(label, n.x!, n.y! + r + 3)
          }
          ctx.textBaseline = 'alphabetic'
        }}
      />

      {/* 색상 범례 */}
      {nodes.length > 1 && minW !== maxW && (
        <div className="absolute top-3 right-3 flex items-center gap-2 bg-white/90 rounded-lg px-3 py-1.5 border border-gray-100 shadow-sm">
          <span className="text-[10px] text-gray-400">{minW}회</span>
          <div className="w-20 h-2 rounded-full" style={{
            background: `linear-gradient(to right, rgb(147,197,253), rgb(99,102,241), rgb(109,40,217))`
          }} />
          <span className="text-[10px] text-gray-400">{maxW}회</span>
        </div>
      )}

      {/* 호버 툴팁 */}
      {hovered && !selected && (
        <div className="absolute top-3 left-3 bg-white rounded-lg shadow-md px-3 py-2 text-xs pointer-events-none border border-gray-100">
          <p className="font-semibold text-gray-800">{hovered.id}</p>
          <p className="text-gray-400 mt-0.5">총 {hovered.weight}회 사용</p>
        </div>
      )}

      {/* 선택 패널 */}
      {selected && (
        <div className="absolute bg-white rounded-xl shadow-lg px-4 py-3 text-xs border border-indigo-100 min-w-[180px] max-w-[240px] z-10" style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
          <div className="flex items-center justify-between gap-2 mb-2">
            <p className="font-semibold text-indigo-700 truncate">{selected.id}</p>
            <button
              onClick={() => setSelected(null)}
              title={TIPS.graph.nodeClose}
              className="text-gray-300 hover:text-gray-500 shrink-0 text-sm leading-none"
            >✕</button>
          </div>
          <p className="text-gray-400 mb-1">
            총 {selected.weight}회 · {(neighborIds?.size ?? 1) - 1}곡과 연결
          </p>
          {selected.lastUsed && (() => {
            const d = daysSince(selected.lastUsed)
            return (
              <p className="text-indigo-400 font-semibold mb-2">
                {`D${d >= 0 ? '+' : ''}${d}`}
                <span className="text-gray-400 font-normal ml-1.5">마지막 사용</span>
              </p>
            )
          })()}
          <div className="space-y-1">
            {selectedLinks.map(l => {
              const partner = l.source === selected.id ? l.target : l.source
              return (
                <div key={partner as string} className="flex items-center justify-between gap-2">
                  <span className="text-gray-600 truncate">{partner as string}</span>
                  <span className="text-indigo-400 shrink-0">×{l.weight}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 페이지 ───────────────────────────────────────────────────────────────────

export function GraphPage() {
  const [minEdge, setMinEdge] = useState(1)

  const { data: history = [], isLoading, isError } = useQuery({
    queryKey: ['history'],
    queryFn: () => fetchHistory(2020),
    staleTime: 60_000,
  })

  const { nodes, links } = useMemo(() => buildGraph(history, minEdge), [history, minEdge])

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 pt-5 pb-4 border-b border-gray-100 flex flex-wrap items-center gap-4">
        <div>
          <h1 className="text-base font-semibold text-gray-800">곡 관계도</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            같은 셋리스트에 함께 사용된 횟수만큼 연결됩니다. 드래그·스크롤로 탐색하세요.
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <label className="text-xs text-gray-500">최소 연결</label>
          <input
            type="number"
            min={1}
            max={20}
            value={minEdge}
            onChange={e => setMinEdge(Math.max(1, Number(e.target.value) || 1))}
            title={TIPS.graph.minEdge}
            className="w-14 border border-gray-300 rounded px-2 py-1 text-xs text-center outline-none focus:border-blue-400"
          />
          <span className="text-xs text-gray-400">{nodes.length}곡 · {links.length}연결</span>
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0">
        {isLoading && (
          <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
            불러오는 중...
          </div>
        )}
        {isError && (
          <div className="m-6 text-sm text-red-500 bg-red-50 rounded p-4">
            이력을 불러올 수 없습니다. 서버 연결을 확인하세요.
          </div>
        )}
        {!isLoading && !isError && history.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
            이력이 없습니다. 이력 탭에서 데이터를 추가하세요.
          </div>
        )}
        {!isLoading && nodes.length === 0 && history.length > 0 && (
          <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
            연결 횟수 {minEdge}회 이상인 곡 쌍이 없습니다.
          </div>
        )}
        {!isLoading && nodes.length > 0 && (
          <GraphCanvas nodes={nodes} links={links} />
        )}
      </div>
    </div>
  )
}
