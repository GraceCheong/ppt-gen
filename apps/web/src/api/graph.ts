import { apiFetch } from './client'

export interface LastUsed {
  visible: boolean
  date: string | null
  dLabel: string | null
}

export interface GraphNode {
  id: string
  weight: number
  lastUsed: LastUsed
}

export interface GraphEdge {
  source: string
  target: string
  weight: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export async function fetchGraph(): Promise<GraphData> {
  return apiFetch<GraphData>('/api/graph')
}
