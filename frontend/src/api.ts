/**
 * API 클라이언트
 */

const API_BASE_URL = 'http://localhost:8000';

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  session_id: string;
  reply_text: string;
  report_id?: string;
  download_url?: string;
}

/**
 * 채팅 메시지 전송
 */
export async function postChat(
  message: string,
  sessionId?: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: sessionId || undefined,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '서버 오류' }));
    throw new Error(error.detail || '채팅 요청 실패');
  }

  return response.json();
}

/**
 * PDF 리포트 다운로드 URL 생성
 */
export function getReportDownloadUrl(reportId: string): string {
  return `${API_BASE_URL}/report/${reportId}`;
}
