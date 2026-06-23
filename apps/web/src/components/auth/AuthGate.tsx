import { useEffect, useState, type ReactNode } from 'react'
import { useAuthStore } from '../../store/authStore'
import { LoginForm } from './LoginForm'
import { SignupForm } from './SignupForm'

type AuthScreen = 'login' | 'signup'

interface AuthGateProps {
  children: ReactNode
}

export function AuthGate({ children }: AuthGateProps) {
  const { mode, checkSession } = useAuthStore()
  const [screen, setScreen] = useState<AuthScreen>('login')

  useEffect(() => {
    checkSession()
  }, [checkSession])

  if (mode === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-gray-400">
        불러오는 중...
      </div>
    )
  }

  // 로그인됐거나 게스트 선택 완료 → 앱 표시
  if (mode === 'user' || mode === 'guest') {
    return <>{children}</>
  }

  // mode === 'unauthenticated' → 로그인/회원가입/Guest 선택 화면
  if (screen === 'signup') {
    return <SignupForm onSwitchToLogin={() => setScreen('login')} />
  }
  return <LoginForm onSwitchToSignup={() => setScreen('signup')} />
}
