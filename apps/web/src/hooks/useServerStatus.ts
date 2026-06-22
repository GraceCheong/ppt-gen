import { useCallback, useEffect, useState } from 'react'
import {
  initServerResolution,
  resetServerResolution,
  type ServerResolution,
} from '../api/serverConfig'

export function useServerStatus() {
  const [resolution, setResolution] = useState<ServerResolution | null>(null)

  useEffect(() => {
    initServerResolution().then(setResolution)
  }, [])

  const reconnect = useCallback(() => {
    setResolution(null)
    resetServerResolution()
    initServerResolution().then(setResolution)
  }, [])

  return { resolution, reconnect }
}
