import { AppShell } from '../components/layout/AppShell'
import { SetlistPanel } from '../components/setlist/SetlistPanel'
import { LyricsEditorPanel } from '../components/editor/LyricsEditorPanel'
import { DeckPanel } from '../components/deck/DeckPanel'

export function AppPage() {
  return (
    <div className="md:h-full">
      <AppShell
        left={<SetlistPanel />}
        center={<LyricsEditorPanel />}
        right={<DeckPanel />}
      />
    </div>
  )
}
