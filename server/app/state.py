"""전역 공유 상태 (ThreadPoolExecutor, asyncio Task 추적).

asyncio.Lock은 이벤트 루프 내에서 생성해야 하므로 lifespan에서 app.state에 붙인다.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

# COM / PPT 작업은 단일 스레드에서 직렬 처리
executor = ThreadPoolExecutor(max_workers=1)
# 템플릿 동기화는 별도 스레드
template_executor = ThreadPoolExecutor(max_workers=1)

# asyncio.Task — lifespan에서 설정/취소
template_sync_task: asyncio.Task | None = None
