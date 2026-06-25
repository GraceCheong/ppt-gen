import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ForceGraph2D from 'react-force-graph-2d'
// @ts-expect-error — d3-force-3d는 force-graph 내부에서 사용하는 패키지이며 타입 선언이 없음
import { forceCollide } from 'd3-force-3d'
import { fetchGraph, type GraphNode, type GraphEdge } from '../api/graph'
import { TIPS } from '../constants/tooltips'
import { GitFork, X, AlertCircle, Loader2 } from 'lucide-react'

// ── 타입 ─────────────────────────────────────────────────────────────────────

type ResolvedLink = Omit<GraphEdge, 'source' | 'target'> & {
  source: GraphNode | string
  target: GraphNode | string
}

function linkId(link: ResolvedLink): [string, string] {
  const s = typeof link.source === 'object' ? link.source.id : link.source
  const t = typeof link.target === 'object' ? link.target.id : link.target
  return [s, t]
}

// ── 상수 ─────────────────────────────────────────────────────────────────────

const NODE_R_MIN       = 5    // 노드 최소 반지름 (px)
const NODE_R_MAX       = 15   // 노드 최대 반지름 (px)
const NODE_R_BASE      = 5    // 반지름 기저값
const NODE_R_SCALE     = 1.5  // weight 당 반지름 증가량
const NODE_HOVER_BONUS = 2    // hover/선택 시 반지름 추가량
const NODE_HIT_PAD     = 10   // 포인터 히트 영역 여유 (px)

const LABEL_MAX_CHARS  = 15   // 레이블 최대 글자 수
const LABEL_FONT_PX    = 7    // 레이블 폰트 크기 (px)
const LABEL_GAP        = 2    // 노드 하단과 레이블 간격 (px)
const LABEL_CHAR_PX    = 5    // 글자당 추정 너비 (px, 충돌 반지름 계산용)

const COLLISION_ITERATIONS = 2   // forceCollide 반복 횟수
const COLLISION_R_PAD      = 8  // 노드 반지름 기준 충돌 여유 (px)
const COLLISION_LABEL_PAD  = 10  // 레이블 영역 아래 여유 (노드 중심 기준, px)
const COLLISION_EXTRA      = 0  // 추가 여유 (px)

const CHARGE_STRENGTH  = -50  // ManyBody force 강도

const ZOOM_DURATION    = 400  // zoomToFit 애니메이션 (ms)
const ZOOM_PADDING     = 100   // zoomToFit 여백 (px)
const CANVAS_MIN_H     = 400  // 캔버스 최소 높이 (px)
const WARMUP_TICKS     = 80
const COOLDOWN_TICKS   = 80
const VELOCITY_DECAY   = 0.4  // 높을수록 드래그 후 빠르게 안정됨 (d3 기본값 0.4)

const LINK_W_MAX       = 50    // 링크 최대 너비 (px)
const LINK_W_BASE      = 0.7  // 링크 기저 너비
const LINK_W_SCALE     = 1.2  // weight 당 너비 증가량

const LINK_ALPHA_BASE  = 0.1  // 기본 링크 투명도 하한
const LINK_ALPHA_SCALE = 0.2  // 기본 링크 투명도 weight 배율
const LINK_ALPHA_MAX   = 0.8  // 기본 링크 투명도 상한
const LINK_SEL_BASE    = 0.2  // 선택 강조 링크 투명도 하한
const LINK_SEL_SCALE   = 0.3  // 선택 강조 링크 투명도 weight 배율
const LINK_SEL_MAX     = 0.9  // 선택 강조 링크 투명도 상한
const LINK_DIM_ALPHA   = 0.08 // 딤 처리 링크 투명도

const SELECTED_LINKS_LIMIT = 6  // 상세 카드에 표시할 연결 곡 최대 수

// ── 색상 스케일 (저빈도 → 고빈도) ────────────────────────────────────────────

const COLOR_STOPS = [
  [147, 197, 253],
  [99,  102, 241],
  [109,  40, 217],
] as const

function lerpColor(t: number): string {
  t = Math.max(0, Math.min(1, t))
  const [from, to, s] = t <= 0.5
    ? [COLOR_STOPS[0], COLOR_STOPS[1], t * 2]
    : [COLOR_STOPS[1], COLOR_STOPS[2], (t - 0.5) * 2]
  const r = Math.round(from[0] + (to[0] - from[0]) * s)
  const g = Math.round(from[1] + (to[1] - from[1]) * s)
  const b = Math.round(from[2] + (to[2] - from[2]) * s)
  return `rgb(${r},${g},${b})`
}

// ── 순수 유틸 — 컴포넌트 외부에 정의 ─────────────────────────────────────────

function nodeR(weight: number): number {
  return Math.max(NODE_R_MIN, Math.min(NODE_R_MAX, NODE_R_BASE + weight * NODE_R_SCALE))
}

function paintPointer(raw: object, color: string, ctx: CanvasRenderingContext2D) {
  const node = raw as GraphNode & { x: number; y: number }
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(node.x, node.y, nodeR(node.weight) + NODE_HIT_PAD, 0, Math.PI * 2)
  ctx.fill()
}

// ── 필터 ─────────────────────────────────────────────────────────────────────

function filterGraph(nodes: GraphNode[], edges: GraphEdge[], minEdge: number) {
  const filtered = edges.filter(e => e.weight >= minEdge)
  const connected = new Set<string>()
  for (const e of filtered) {
    connected.add(e.source)
    connected.add(e.target)
  }
  return {
    nodes: nodes.filter(n => connected.has(n.id)),
    links: filtered,
  }
}

// ── 캔버스 컴포넌트 ───────────────────────────────────────────────────────────

function GraphCanvas({ nodes, links }: { nodes: GraphNode[]; links: GraphEdge[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null)
  const fitDone = useRef(false)

  const [dim, setDim] = useState<{ w: number; h: number } | null>(null)
  const [hovered, setHovered] = useState<GraphNode | null>(null)
  const [selected, setSelected] = useState<GraphNode | null>(null)

  // nodes/links 레퍼런스가 바뀌어도 graphData 객체는 안정적으로 유지 → hover 시 시뮬 리셋 방지
  const graphData = useMemo(() => ({ nodes, links }), [nodes, links])

  // 컨테이너 크기 관찰
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width > 0) setDim({ w: width, h: Math.max(CANVAS_MIN_H, height) })
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // 탭 복귀 등 dim 변경 시 그래프를 뷰포트에 맞춤
  useEffect(() => {
    if (!dim || !graphRef.current) return
    fitDone.current = false
    graphRef.current.zoomToFit(ZOOM_DURATION, ZOOM_PADDING)
  }, [dim])

  // charge strength — 파라미터만 바꾸는 단순 setter, 렌더링마다 실행해도 시뮬 안 건드림
  useEffect(() => {
    graphRef.current?.d3Force('charge')?.strength(CHARGE_STRENGTH)
  })

  // collision force + reheat — 데이터 변경 시에만 실행 (새 force 객체 생성 → initialize 호출)
  useEffect(() => {
    const g = graphRef.current
    if (!g) return
    g.d3Force(
      'collision',
      forceCollide((node: GraphNode) => {
        const r = nodeR(node.weight)
        const labelHalfW = (Math.min(node.id.length, LABEL_MAX_CHARS) * LABEL_CHAR_PX) / 2
        return Math.max(r + COLLISION_R_PAD, labelHalfW, r + COLLISION_LABEL_PAD) + COLLISION_EXTRA
      }).iterations(COLLISION_ITERATIONS),
    )
    fitDone.current = false
    g.d3ReheatSimulation()
  }, [nodes, links])

  // min/max weight → 색상 스케일 계산
  const { minW, maxW } = useMemo(() => {
    if (!nodes.length) return { minW: 0, maxW: 1 }
    let min = Infinity, max = -Infinity
    for (const n of nodes) {
      if (n.weight < min) min = n.weight
      if (n.weight > max) max = n.weight
    }
    return { minW: min, maxW: max }
  }, [nodes])

  const nodeColor = useCallback(
    (weight: number) => maxW === minW ? lerpColor(0.5) : lerpColor((weight - minW) / (maxW - minW)),
    [minW, maxW],
  )

  // 선택된 노드의 이웃 집합 (딤 처리 기준)
  const neighborIds = useMemo<Set<string> | null>(() => {
    if (!selected) return null
    const ids = new Set<string>([selected.id])
    for (const l of links) {
      if (l.source === selected.id) ids.add(l.target as string)
      if (l.target === selected.id) ids.add(l.source as string)
    }
    return ids
  }, [selected, links])

  // 선택 노드와 연결된 상위 N개 링크
  const selectedLinks = useMemo(() =>
    selected
      ? links
          .filter(l => l.source === selected.id || l.target === selected.id)
          .sort((a, b) => b.weight - a.weight)
          .slice(0, SELECTED_LINKS_LIMIT)
      : [],
    [selected, links],
  )

  // 노드 캔버스 페인터
  const paintNode = useCallback((raw: object, ctx: CanvasRenderingContext2D) => {
    const node = raw as GraphNode & { x: number; y: number }
    const r = nodeR(node.weight)
    const dimmed = neighborIds !== null && !neighborIds.has(node.id)
    const isSel = selected?.id === node.id
    const isHov = hovered?.id === node.id

    ctx.beginPath()
    ctx.arc(node.x, node.y, r + (isSel || isHov ? NODE_HOVER_BONUS : 0), 0, Math.PI * 2)
    ctx.fillStyle = dimmed
      ? 'rgba(200,200,215,0.3)'
      : isSel  ? '#4f46e5'
      : isHov  ? '#818cf8'
      : nodeColor(node.weight)
    ctx.fill()

    if (isSel || isHov) {
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = NODE_HOVER_BONUS
      ctx.stroke()
    }
  }, [neighborIds, selected?.id, hovered?.id, nodeColor])

  // 레이블 오버레이 (노드 아래)
  const renderLabels = useCallback((ctx: CanvasRenderingContext2D) => {
    for (const node of nodes) {
      const n = node as GraphNode & { x?: number; y?: number }
      if (n.x == null) continue
      const dimmed = neighborIds !== null && !neighborIds.has(n.id)
      const isSel = selected?.id === n.id
      const isHov = hovered?.id === n.id
      ctx.font = `${isSel || isHov ? 'bold ' : ''}${LABEL_FONT_PX}px sans-serif`
      ctx.fillStyle = dimmed ? 'rgba(180,180,200,0.4)' : '#3f3f46'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      const label = n.id.length > LABEL_MAX_CHARS ? n.id.slice(0, LABEL_MAX_CHARS - 1) + '…' : n.id
      ctx.fillText(label, n.x!, n.y! + nodeR(n.weight) + LABEL_GAP)
    }
    ctx.textBaseline = 'alphabetic'
  }, [nodes, neighborIds, selected?.id, hovered?.id])

  return (
    <div ref={containerRef} className="relative flex-1 min-h-0 overflow-hidden bg-neutral-50/10">
      {dim && (
        <ForceGraph2D
          ref={graphRef}
          width={dim.w}
          height={dim.h}
          graphData={graphData}
          nodeId="id"
          nodeCanvasObject={paintNode}
          nodeCanvasObjectMode={() => 'replace'}
          nodePointerAreaPaint={paintPointer}
          linkWidth={(l) => Math.min(LINK_W_MAX, LINK_W_BASE + (l as GraphEdge).weight * LINK_W_SCALE)}
          linkColor={(l) => {
            const link = l as ResolvedLink
            const [s, t] = linkId(link)
            const w = link.weight
            if (!neighborIds) return `rgba(99,102,241,${Math.min(LINK_ALPHA_MAX, LINK_ALPHA_BASE + w * LINK_ALPHA_SCALE)})`
            return neighborIds.has(s) && neighborIds.has(t)
              ? `rgba(99,102,241,${Math.min(LINK_SEL_MAX, LINK_SEL_BASE + w * LINK_SEL_SCALE)})`
              : `rgba(200,200,220,${LINK_DIM_ALPHA})`
          }}
          linkDirectionalArrowLength={0}
          onNodeHover={(node) => setHovered(node as GraphNode | null)}
          onNodeClick={(node) => {
            const n = node as GraphNode
            setSelected(prev => prev?.id === n.id ? null : n)
          }}
          onBackgroundClick={() => setSelected(null)}
          onEngineStop={() => {
            if (!fitDone.current) {
              fitDone.current = true
              graphRef.current?.zoomToFit(ZOOM_DURATION, ZOOM_PADDING)
            }
          }}
          warmupTicks={WARMUP_TICKS}
          cooldownTicks={COOLDOWN_TICKS}
          d3VelocityDecay={VELOCITY_DECAY}
          backgroundColor="#ffffff"
          onRenderFramePost={renderLabels}
        />
      )}

      {/* 색상 범례 */}
      {nodes.length > 1 && minW !== maxW && (
        <div className="absolute top-4 right-4 flex items-center gap-2.5 bg-white/95 backdrop-blur-xs rounded-xl px-3.5 py-2 border border-neutral-200/60 shadow-md select-none">
          <span className="text-[10px] font-bold text-neutral-400">{minW}회</span>
          <div className="w-20 h-1.5 rounded-full" style={{
            background: 'linear-gradient(to right, rgb(147,197,253), rgb(99,102,241), rgb(109,40,217))'
          }} />
          <span className="text-[10px] font-bold text-neutral-400">{maxW}회</span>
        </div>
      )}

      {/* 호버 툴팁 — 선택 중일 때는 숨김 */}
      {hovered && !selected && (
        <div className="absolute top-4 left-4 bg-neutral-900 text-white rounded-xl shadow-lg px-3.5 py-2.5 text-xs pointer-events-none border border-neutral-800/80 animate-in fade-in duration-100 select-none">
          <p className="font-bold">{hovered.id}</p>
          <p className="text-[10px] text-neutral-400 mt-0.5">총 {hovered.weight}회 예배에 사용됨</p>
        </div>
      )}

      {/* 선택 상세 카드 */}
      {selected && (
        <div
          className="absolute bg-white/95 backdrop-blur-xs rounded-2xl shadow-xl px-4 py-4 text-xs border border-neutral-200/80 min-w-[200px] max-w-[240px] z-10 select-none flex flex-col gap-3"
          style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
        >
          <div className="flex items-center justify-between gap-3 pb-2 border-b border-neutral-100">
            <p className="font-bold text-primary-600 truncate">{selected.id}</p>
            <button
              onClick={() => setSelected(null)}
              title={TIPS.graph.nodeClose}
              className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100 rounded-lg p-1 transition-colors shrink-0 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="text-[11px] leading-relaxed text-neutral-500 space-y-1">
            <p className="font-semibold text-neutral-700">
              총 <span className="text-primary-600 font-bold">{selected.weight}회</span> 사용
            </p>
            <p className="text-[10px]">
              {(neighborIds?.size ?? 1) - 1}개 찬양과 동시 수록
            </p>
            {selected.lastUsed.visible && selected.lastUsed.dLabel && (
              <p className="text-primary-500 font-bold mt-1 bg-primary-50 rounded px-2 py-0.5 border border-primary-100/30 text-[10px] inline-block">
                {selected.lastUsed.dLabel} 마지막 사용
              </p>
            )}
          </div>

          {selectedLinks.length > 0 && (
            <div className="space-y-1.5 pt-2 border-t border-neutral-100">
              <p className="text-[9px] font-bold text-neutral-400 uppercase tracking-wider">주요 연결 곡 (공동 편성)</p>
              <div className="space-y-1 max-h-[120px] overflow-y-auto pr-1">
                {selectedLinks.map(l => {
                  const partner = l.source === selected.id ? l.target : l.source
                  return (
                    <div key={partner as string} className="flex items-center justify-between gap-3 text-[11px] py-0.5">
                      <span className="text-neutral-600 truncate font-medium">{partner as string}</span>
                      <span className="text-primary-500 shrink-0 font-bold">×{l.weight}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── 페이지 ───────────────────────────────────────────────────────────────────

export function GraphPage() {
  const [minEdge, setMinEdge] = useState(1)

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ['graph'],
    queryFn: fetchGraph,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
  })

  const { nodes, links } = useMemo(
    () => filterGraph(data?.nodes ?? [], data?.edges ?? [], minEdge),
    [data, minEdge],
  )

  return (
    <div className="flex flex-col h-full bg-white select-none">
      <div className="px-6 py-4 border-b border-neutral-200 flex flex-wrap items-center gap-4 bg-neutral-50/20">
        <div>
          <div className="flex items-center gap-1.5 text-sm font-bold text-neutral-800">
            <GitFork className="w-4 h-4 text-primary-500" />
            <span>찬양 콘티 그래프</span>
          </div>
          <p className="text-[10px] text-neutral-400 mt-0.5">
            같은 셋리스트에 동시 편성된 횟수가 많을수록 긴밀하게 연결됩니다. 드래그나 휠 스크롤로 관계도를 탐색하세요.
          </p>
        </div>

        <div className="ml-auto flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2">
            <label className="text-[11px] font-bold text-neutral-500">최소 공동 수록 횟수</label>
            <input
              type="number"
              min={1}
              max={20}
              value={minEdge}
              onChange={e => setMinEdge(Math.max(1, Number(e.target.value) || 1))}
              title={TIPS.graph.minEdge}
              className="w-14 border border-neutral-200 rounded-lg px-2 py-1 text-xs font-bold text-center outline-none bg-white hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all text-neutral-800"
            />
          </div>
          <span className="text-[10px] font-bold text-neutral-400 bg-neutral-100 border border-neutral-200/50 rounded-full px-2.5 py-0.5">
            {nodes.length}곡 구성 · {links.length}연결 관계
          </span>
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0">
        {(isLoading || (isFetching && nodes.length === 0)) && (
          <div className="flex-1 flex flex-col items-center justify-center text-xs text-neutral-400 gap-2">
            <Loader2 className="w-5 h-5 text-primary-500 animate-spin" />
            <span>불러오는 중...</span>
          </div>
        )}
        {!isLoading && !isFetching && isError && (
          <div className="m-5 text-xs text-danger-700 bg-danger-50 border border-danger-100 rounded-xl p-4 flex items-start gap-2.5 font-medium leading-normal">
            <AlertCircle className="w-4 h-4 text-danger-500 shrink-0 mt-0.5" />
            <span>그래프 데이터를 불러올 수 없습니다. 인터넷이나 서버 상태를 확인해 주세요.</span>
          </div>
        )}
        {!isLoading && !isFetching && !isError && (data?.nodes.length ?? 0) === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-xs text-neutral-400 gap-2">
            <AlertCircle className="w-5 h-5 text-neutral-300 animate-pulse" />
            <span>분석할 예배 이력이 없습니다. 먼저 캘린더나 이력 탭에서 데이터를 기록하세요.</span>
          </div>
        )}
        {!isLoading && !isFetching && nodes.length === 0 && (data?.nodes.length ?? 0) > 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-xs text-neutral-400 gap-2">
            <AlertCircle className="w-5 h-5 text-neutral-300 animate-pulse" />
            <span>최소 공동 수록 횟수가 {minEdge}회 이상 연결된 찬양 조합이 없습니다. 설정값을 조절해 보세요.</span>
          </div>
        )}
        {!isLoading && nodes.length > 0 && (
          <GraphCanvas nodes={nodes} links={links} />
        )}
      </div>
    </div>
  )
}
