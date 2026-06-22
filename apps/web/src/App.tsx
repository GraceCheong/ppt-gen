import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Header } from './components/layout/Header'
import { AppPage } from './pages/AppPage'
import { HistoryPage } from './pages/HistoryPage'
import { initServerResolution } from './api/serverConfig'
import './index.css'

// react-force-graph-2d가 크므로 관계도 페이지는 lazy load
const GraphPage = lazy(() => import('./pages/GraphPage').then(m => ({ default: m.GraphPage })))

initServerResolution()

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

function RootLayout() {
  return (
    <div className="flex flex-col h-screen">
      <Header />
      <div className="flex-1 min-h-0 md:overflow-hidden overflow-y-auto">
        <Outlet />
      </div>
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<RootLayout />}>
            <Route path="/app" element={<AppPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route
              path="/graph"
              element={
                <Suspense fallback={
                  <div className="flex-1 flex items-center justify-center h-full text-sm text-gray-400">
                    로딩 중...
                  </div>
                }>
                  <GraphPage />
                </Suspense>
              }
            />
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
