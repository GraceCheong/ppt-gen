import logging

from fastapi import APIRouter, HTTPException, Request

from server.app.services.error_report_service import sanitize_report, save_error_report

logger = logging.getLogger("ppt_gen.server")
router = APIRouter()


@router.post("/client-error-report")
@router.post("/api/client-error-report")
async def client_error_report(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"오류 리포트 JSON 형식이 올바르지 않습니다: {e}")

    if not isinstance(data, dict):
        raise HTTPException(400, detail="오류 리포트는 JSON object여야 합니다.")

    report = sanitize_report(data, request)
    file_path = save_error_report(report)
    logger.info(
        "[client-error-report] context=%s message=%s saved=%s",
        report.get("context"),
        report.get("message"),
        file_path,
    )
    return {"status": "ok"}
