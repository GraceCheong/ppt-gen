import type { ReactNode } from 'react'

interface AppShellProps {
  left: ReactNode
  center: ReactNode
  right: ReactNode
}

export function AppShell({ left, center, right }: AppShellProps) {
  return (
    <>
      {/* 데스크탑: 3단 고정 레이아웃 */}
      <div className="hidden md:flex h-full overflow-hidden">
        <aside className="w-64 shrink-0 border-r border-gray-200 bg-white overflow-y-auto flex flex-col">
          {left}
        </aside>
        <main className="flex-1 overflow-y-auto bg-white">
          {center}
        </main>
        <aside className="w-72 shrink-0 border-l border-gray-200 bg-white overflow-y-auto flex flex-col">
          {right}
        </aside>
      </div>

      {/* 모바일: 세로 카드 배치 — 패널마다 뷰포트 높이 지정해 내부 스크롤 작동 */}
      <div className="md:hidden flex flex-col divide-y divide-gray-200 bg-gray-50">
        <div className="h-[45dvh] bg-white flex flex-col">{left}</div>
        <div className="h-[65dvh] bg-white flex flex-col">{center}</div>
        <div className="bg-white flex flex-col">{right}</div>
      </div>
    </>
  )
}
