"""User-facing connection and readiness messages (C14)."""

from __future__ import annotations

from core.llm.types import ConnResult


def format_connection_result(result: ConnResult) -> str:
    if result.success:
        return f"연결 성공: {result.message}"
    message = result.message.lower()
    if any(token in message for token in ("401", "403", "unauthorized", "authentication", "api key")):
        return "인증 실패: API 키 또는 권한을 확인하세요."
    if any(
        token in message
        for token in ("connection refused", "failed to establish", "name or service not known", "timed out")
    ):
        return f"네트워크 오류: 서버 URL과 연결 상태를 확인하세요. ({result.message})"
    if "404" in message or "not found" in message:
        return f"엔드포인트 오류: Base URL을 확인하세요. ({result.message})"
    return f"연결 실패: {result.message}"
