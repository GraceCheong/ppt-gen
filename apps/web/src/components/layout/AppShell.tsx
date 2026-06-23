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
        <aside className="w-68 shrink-0 border-r border-neutral-200 bg-white overflow-y-auto flex flex-col shadow-sm z-1">
          {left}
        </aside>
        <main className="flex-1 overflow-y-auto bg-neutral-50/20">
          {center}
        </main>
        <aside className="w-76 shrink-0 border-l border-neutral-200 bg-white overflow-y-auto flex flex-col shadow-sm z-1">
          {right}
        </aside>
      </div>

      {/* 모바일: 세로 카드 배치 — 패널마다 뷰포트 높이 지정해 내부 스크롤 작동 */}
      <div className="md:hidden flex flex-col divide-y divide-neutral-200 bg-neutral-50">
        <div className="h-[45dvh] bg-white flex flex-col">{left}</div>
        <div className="h-[65dvh] bg-white flex flex-col">{center}</div>
        <div className="bg-white flex flex-col">{right}</div>
      </div>
    </>
  )
}

