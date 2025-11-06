import { useState, useEffect, useRef } from 'react';
import { postChat, getReportDownloadUrl } from './api';
import './App.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  reportId?: string;
  downloadUrl?: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 세션 ID를 세션스토리지에 저장/복원 (탭 별 독립 세션 유지)
  useEffect(() => {
    const savedSessionId = sessionStorage.getItem('sessionId');
    if (savedSessionId) {
      setSessionId(savedSessionId);
    }
  }, []);

  // 메시지 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');

    // 사용자 메시지 추가
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      // API 호출
      const response = await postChat(userMessage, sessionId || undefined);

      // 세션 ID 저장
      if (!sessionId) {
        setSessionId(response.session_id);
        sessionStorage.setItem('sessionId', response.session_id);
      }

      // 어시스턴트 메시지 추가
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.reply_text,
          reportId: response.report_id,
          downloadUrl: response.download_url,
        },
      ]);
    } catch (error) {
      console.error('Chat error:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `오류: ${error instanceof Error ? error.message : '알 수 없는 오류'}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setSessionId(null);
    sessionStorage.removeItem('sessionId');
  };

  return (
    <div className="app">
      <header className="header">
        <h1>커머스 마케팅 에이전트</h1>
        <button onClick={handleNewChat} className="new-chat-btn">
          새 대화
        </button>
      </header>

      <div className="chat-container">
        <div className="messages">
          {messages.length === 0 && (
            <div className="welcome">
              <p>커머스 마케팅 분석을 도와드립니다.</p>
              <p className="example">
                예시: "에어팟 프로 구매자를 세그먼트로 분류해줘"
              </p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-content">
                <div className="message-text">{msg.content}</div>
                {msg.downloadUrl && msg.reportId && (
                  <a
                    href={getReportDownloadUrl(msg.reportId)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="download-btn"
                  >
                    PDF 다운로드
                  </a>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="message assistant">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="메시지를 입력하세요..."
            disabled={isLoading}
            rows={3}
          />
          <button onClick={handleSend} disabled={isLoading || !input.trim()}>
            전송
          </button>
        </div>
      </div>

      <footer className="footer">
        <p>⚠️ 본 결과는 연구·교육용이며 실제 마케팅 전략 수립 시 전문가와 상담하시기 바랍니다.</p>
      </footer>
    </div>
  );
}

export default App;
