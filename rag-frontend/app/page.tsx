"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { MenuIcon } from "../components/MenuIcon";
import styles from "./page.module.css";
import {
  apiBaseUrl,
  ChatResponse,
  DeleteSessionResponse,
  KnowledgeBaseResponse,
  MessageResponse,
  SessionListResponse,
  SessionMessagesResponse,
  SessionResponse,
  UserResponse,
} from "../lib/api";
import {
  AuthError,
  authFetch,
  clearStoredAuth,
  fetchCurrentUser,
  getStoredAuth,
} from "../lib/auth";

const starterQuestions = [
  "这个系统里谁负责控制流程走向？",
  "LangGraph 在这个项目中起什么作用？",
  "你好，你是谁？",
];

type StreamEvent = {
  type: string;
  data: Record<string, unknown>;
};

export default function HomePage() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(4);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseResponse[]>([]);
  const [selectedKnowledgeBaseIds, setSelectedKnowledgeBaseIds] = useState<string[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState("");
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [bootLoading, setBootLoading] = useState(true);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameTitle, setRenameTitle] = useState("");
  const [renameLoading, setRenameLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [knowledgeBasePickerOpen, setKnowledgeBasePickerOpen] = useState(false);
  const [error, setError] = useState("");
  const [sessionKeyword, setSessionKeyword] = useState("");
  const [menuSessionId, setMenuSessionId] = useState("");
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const chatCanvasRef = useRef<HTMLDivElement | null>(null);
  const isUserScrolledUpRef = useRef(false);

  useEffect(() => {
    void bootstrap();
  }, []);

  // 监听用户手动滚动：如果在底部附近则允许自动滚动，否则禁止
  useEffect(() => {
    const el = chatCanvasRef.current;
    if (!el) return;
    const handleScroll = () => {
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      isUserScrolledUpRef.current = distanceFromBottom > 100;
    };
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (isUserScrolledUpRef.current) return;
    const el = chatCanvasRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [messages]);

  useEffect(() => {
    if (!menuSessionId) return;
    const close = () => setMenuSessionId("");
    document.addEventListener("click", close, true);
    return () => document.removeEventListener("click", close, true);
  }, [menuSessionId]);

  const currentSession = useMemo(
    () => sessions.find((item) => item.id === currentSessionId) ?? null,
    [currentSessionId, sessions],
  );

  const selectedKnowledgeBases = useMemo(
    () => knowledgeBases.filter((item) => selectedKnowledgeBaseIds.includes(item.id)),
    [knowledgeBases, selectedKnowledgeBaseIds],
  );

  const selectedKnowledgeBaseSummary = useMemo(() => {
    if (selectedKnowledgeBaseIds.length === 0) return "全部知识库";
    if (selectedKnowledgeBases.length === 0) return "未匹配到知识库";
    return selectedKnowledgeBases.map((item) => item.name).join("、");
  }, [selectedKnowledgeBaseIds.length, selectedKnowledgeBases]);

  const filteredSessions = useMemo(() => {
    const keyword = sessionKeyword.trim().toLowerCase();
    if (!keyword) return sessions;
    return sessions.filter((session) => {
      const title = session.title.toLowerCase();
      const kb = (session.knowledge_base_name || "").toLowerCase();
      return title.includes(keyword) || kb.includes(keyword);
    });
  }, [sessionKeyword, sessions]);

  // ========================== Logic (unchanged) ==========================

  function buildTempMessage(id: number, role: "user" | "assistant", content: string): MessageResponse {
    return { id, session_id: currentSessionId, role, content, route: "", retrieval_quality: "", rewritten_question: "", standalone_question: "", source_count: 0, sources: [], steps: [], created_at: new Date().toISOString() };
  }

  function updateTempAssistantMessage(tempId: number, content: string) {
    setMessages((current) => current.map((item) => (item.id === tempId ? { ...item, content } : item)));
  }

  async function bootstrap() {
    setBootLoading(true);
    setError("");
    try {
      const auth = getStoredAuth();
      if (!auth) { router.replace("/login"); return; }
      const user = await fetchCurrentUser();
      setCurrentUser(user);
      const [knowledgeBaseList, loadedSessions] = await Promise.all([fetchKnowledgeBases(), fetchSessions()]);
      setKnowledgeBases(knowledgeBaseList);
      setSelectedKnowledgeBaseIds([]);
      if (loadedSessions.length > 0) {
        setSessions(loadedSessions);
        await selectSession(loadedSessions[0].id, loadedSessions);
      } else {
        const created = await createSession();
        setSessions([created]);
        await selectSession(created.id, [created]);
      }
    } catch (bootstrapError) {
      handleAuthAwareError(bootstrapError, "初始化聊天页失败，请检查后端服务。");
    } finally {
      setBootLoading(false);
    }
  }

  function handleAuthAwareError(errorValue: unknown, fallbackMessage: string) {
    if (errorValue instanceof AuthError) { clearStoredAuth(); router.replace("/login"); return; }
    setError(errorValue instanceof Error ? errorValue.message : fallbackMessage);
  }

  async function fetchKnowledgeBases() {
    const response = await authFetch(`${apiBaseUrl}/knowledge-bases`);
    const payload = (await response.json()) as KnowledgeBaseResponse[] | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "获取知识库列表失败。");
    return payload as KnowledgeBaseResponse[];
  }

  async function fetchSessions() {
    const response = await authFetch(`${apiBaseUrl}/sessions`);
    const payload = (await response.json()) as SessionListResponse | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "获取会话列表失败。");
    return (payload as SessionListResponse).sessions;
  }

  async function createSession() {
    const response = await authFetch(`${apiBaseUrl}/sessions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "" }) });
    const payload = (await response.json()) as SessionResponse | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "创建会话失败。");
    return payload as SessionResponse;
  }

  async function fetchSessionMessages(sessionId: string) {
    const response = await authFetch(`${apiBaseUrl}/sessions/${sessionId}/messages`);
    const payload = (await response.json()) as SessionMessagesResponse | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "获取会话消息失败。");
    return payload as SessionMessagesResponse;
  }

  async function selectSession(sessionId: string, currentSessions: SessionResponse[] = sessions) {
    isUserScrolledUpRef.current = false;
    setSessionLoading(true);
    setError("");
    try {
      const payload = await fetchSessionMessages(sessionId);
      setCurrentSessionId(sessionId);
      setMessages(payload.messages);
      setSessions(currentSessions);
      setRenameTitle(payload.session.title);
      setRenaming(false);
      setMenuSessionId("");
      const chosenIds = payload.session.knowledge_base_id ? [payload.session.knowledge_base_id] : [];
      setSelectedKnowledgeBaseIds(chosenIds);
      const latestAssistant = [...payload.messages].reverse().find((item) => item.role === "assistant");
      if (latestAssistant) {
        setResult({ answer: latestAssistant.content, sources: latestAssistant.sources, route: latestAssistant.route, steps: latestAssistant.steps, retrieval_quality: latestAssistant.retrieval_quality, rewritten_question: latestAssistant.rewritten_question, standalone_question: latestAssistant.standalone_question });
      } else {
        setResult(null);
      }
    } catch (selectError) {
      handleAuthAwareError(selectError, "切换会话失败。");
    } finally {
      setSessionLoading(false);
    }
  }

  async function handleCreateSession() {
    setError("");
    try {
      const created = await createSession();
      const nextSessions = [created, ...sessions];
      setSessions(nextSessions);
      setCurrentSessionId(created.id);
      setMessages([]);
      setResult(null);
      setQuestion("");
      setRenameTitle(created.title);
      setRenaming(false);
      setMenuSessionId("");
    } catch (createError) {
      handleAuthAwareError(createError, "新建会话失败。");
    }
  }

  async function handleRenameSession(sessionId: string = currentSessionId) {
    const trimmedTitle = renameTitle.trim();
    if (!sessionId || !trimmedTitle) { setError("请输入会话标题。"); return; }
    setRenameLoading(true);
    setError("");
    try {
      const response = await authFetch(`${apiBaseUrl}/sessions/${sessionId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: trimmedTitle }) });
      const payload = (await response.json()) as SessionResponse | { detail?: string };
      if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "重命名会话失败。");
      const updated = payload as SessionResponse;
      setSessions((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      if (updated.id === currentSessionId) setRenameTitle(updated.title);
      setRenaming(false);
      setMenuSessionId("");
    } catch (renameError) {
      handleAuthAwareError(renameError, "重命名会话失败。");
    } finally {
      setRenameLoading(false);
    }
  }

  async function handleDeleteSession(sessionId: string = currentSessionId) {
    if (!sessionId) return;
    setDeleteLoading(true);
    setError("");
    try {
      const response = await authFetch(`${apiBaseUrl}/sessions/${sessionId}`, { method: "DELETE" });
      const payload = (await response.json()) as DeleteSessionResponse | { detail?: string };
      if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "删除会话失败。");
      const nextSessions = sessions.filter((item) => item.id !== sessionId);
      setSessions(nextSessions);
      setMenuSessionId("");
      if (sessionId === currentSessionId) {
        if (nextSessions.length > 0) { await selectSession(nextSessions[0].id, nextSessions); }
        else { const created = await createSession(); setSessions([created]); await selectSession(created.id, [created]); }
      }
    } catch (deleteError) {
      handleAuthAwareError(deleteError, "删除会话失败。");
    } finally {
      setDeleteLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;
    if (!currentSessionId) { setError("当前没有可用会话，请先新建会话。"); return; }
    isUserScrolledUpRef.current = false; // 用户主动发送时，强制跟随滚动
    setLoading(true);
    setError("");
    try {
      const auth = getStoredAuth();
      if (!auth?.token) throw new AuthError("登录状态已失效，请重新登录。");
      const tempUserId = Date.now();
      const tempAssistantId = tempUserId + 1;
      const userMessage = buildTempMessage(tempUserId, "user", trimmedQuestion);
      const assistantMessage = buildTempMessage(tempAssistantId, "assistant", "");
      setMessages((current) => [...current, userMessage, assistantMessage]);
      setResult({ answer: "", sources: [], route: "", steps: [], retrieval_quality: "", rewritten_question: "", standalone_question: "" });
      setQuestion("");
      const controller = new AbortController();
      setAbortController(controller);
      const response = await fetch(`${apiBaseUrl}/sessions/${currentSessionId}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
        body: JSON.stringify({ question: trimmedQuestion, top_k: topK, knowledge_base_ids: selectedKnowledgeBaseIds }),
        signal: controller.signal,
      });
      if (!response.ok) { const payload = (await response.json()) as { detail?: string }; throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "请求失败。"); }
      if (!response.body) throw new Error("流式响应为空。");
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let answerBuffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const rawLine of lines) {
          const line = rawLine.trim();
          if (!line) continue;
          const eventPayload = JSON.parse(line) as StreamEvent;
          if (eventPayload.type === "step") {
            const step = String(eventPayload.data.step ?? "");
            setResult((current) => { const base = current ?? { answer: answerBuffer, sources: [], route: "", steps: [], retrieval_quality: "", rewritten_question: "", standalone_question: "" }; return { ...base, answer: answerBuffer, route: String(eventPayload.data.route ?? "") || base.route, retrieval_quality: String(eventPayload.data.retrieval_quality ?? "") || base.retrieval_quality, steps: step && !base.steps.includes(step) ? [...base.steps, step] : base.steps }; });
          } else if (eventPayload.type === "sources") {
            const nextSources = Array.isArray(eventPayload.data.sources) ? (eventPayload.data.sources as ChatResponse["sources"]) : [];
            setResult((current) => { const base = current ?? { answer: answerBuffer, sources: [], route: "", steps: [], retrieval_quality: "", rewritten_question: "", standalone_question: "" }; return { ...base, answer: answerBuffer, sources: nextSources }; });
          } else if (eventPayload.type === "meta") {
            setResult((current) => { const base = current ?? { answer: answerBuffer, sources: [], route: "", steps: [], retrieval_quality: "", rewritten_question: "", standalone_question: "" }; return { ...base, answer: answerBuffer, rewritten_question: String(eventPayload.data.rewritten_question ?? "") || base.rewritten_question, standalone_question: String(eventPayload.data.standalone_question ?? "") || base.standalone_question }; });
          } else if (eventPayload.type === "token") {
            const content = String(eventPayload.data.content ?? "");
            if (!content) continue;
            answerBuffer += content;
            updateTempAssistantMessage(tempAssistantId, answerBuffer);
            setResult((current) => { const base = current ?? { answer: "", sources: [], route: "", steps: [], retrieval_quality: "", rewritten_question: "", standalone_question: "" }; return { ...base, answer: answerBuffer }; });
          } else if (eventPayload.type === "final") {
            const finalPayload = eventPayload.data as unknown as ChatResponse;
            answerBuffer = finalPayload.answer;
            updateTempAssistantMessage(tempAssistantId, finalPayload.answer);
            setResult(finalPayload);
          } else if (eventPayload.type === "error") {
            throw new Error(String(eventPayload.data.message ?? "流式回答失败。"));
          }
        }
      }
      const trailingLine = buffer.trim();
      if (trailingLine) {
        const eventPayload = JSON.parse(trailingLine) as StreamEvent;
        if (eventPayload.type === "final") { const finalPayload = eventPayload.data as unknown as ChatResponse; answerBuffer = finalPayload.answer; updateTempAssistantMessage(tempAssistantId, finalPayload.answer); setResult(finalPayload); }
      }
      const updatedSessions = await fetchSessions();
      setSessions(updatedSessions);
      const updatedMessages = await fetchSessionMessages(currentSessionId);
      setMessages(updatedMessages.messages);
    } catch (submitError) {
      if (submitError instanceof DOMException && submitError.name === "AbortError") {
        // User cancelled — silently handled
      } else {
        handleAuthAwareError(submitError, "请求失败，请稍后重试。");
      }
    } finally {
      setLoading(false);
      setAbortController(null);
    }
  }

  function handleLogout() { clearStoredAuth(); router.replace("/login"); }

  function toggleKnowledgeBaseSelection(knowledgeBaseId: string) {
    setSelectedKnowledgeBaseIds((current) => current.includes(knowledgeBaseId) ? current.filter((item) => item !== knowledgeBaseId) : [...current, knowledgeBaseId]);
  }

  async function openRenameForSession(session: SessionResponse) {
    if (session.id !== currentSessionId) await selectSession(session.id);
    setRenameTitle(session.title);
    setRenaming(true);
    setMenuSessionId("");
  }

  async function openDeleteForSession(session: SessionResponse) {
    if (session.id !== currentSessionId) await selectSession(session.id);
    await handleDeleteSession(session.id);
  }

  // ========================== View ==========================

  return (
    <main className={styles.page}>
      <div className={styles.layout}>
        {/* ===== Sidebar ===== */}
        <aside className={styles.sidebar}>
          <div className={styles.brand}>
            <span className={styles.brandMark}>M</span>
            <div className={styles.brandText}>
              <strong>myAgent</strong>
              <small>Knowledge Agent</small>
            </div>
          </div>

          <p className={styles.navLabel}>导航</p>
          <div className={styles.menuList}>
            <button
              className={styles.menuItem}
              onClick={() => void handleCreateSession()}
              type="button"
            >
              <span className={styles.menuIcon}><MenuIcon variant="chat" /></span>
              新建对话
            </button>
            {currentUser?.role === "admin" ? (
              <Link className={styles.menuItem} href="/admin">
                <span className={styles.menuIcon}><MenuIcon variant="grid" /></span>
                管理后台
              </Link>
            ) : null}
          </div>

          <div className={styles.searchCard}>
            <input
              className={styles.searchInput}
              onChange={(event) => setSessionKeyword(event.target.value)}
              placeholder="搜索历史对话..."
              value={sessionKeyword}
            />
          </div>

          <div className={styles.sessionList}>
            <div className={styles.sessionListInner}>
              {filteredSessions.map((session) => {
                const active = session.id === currentSessionId;
                const menuOpen = menuSessionId === session.id;
                return (
                  <div className={active ? styles.sessionRowActive : styles.sessionRow} key={session.id} style={{ position: "relative" }}>
                    <button className={styles.sessionMain} onClick={() => void selectSession(session.id)} type="button">
                      <span className={styles.sessionTitle}>{session.title}</span>
                      <span className={styles.sessionMeta}>{session.message_count} 条消息</span>
                    </button>
                    <button
                      className={menuOpen ? styles.sessionMenuButtonActive : styles.sessionMenuButton}
                      onClick={() => setMenuSessionId((current) => (current === session.id ? "" : session.id))}
                      type="button"
                    >...</button>
                    {menuOpen ? (
                      <div className={styles.sessionMenu}>
                        <button className={styles.sessionMenuItem} onClick={() => void openRenameForSession(session)} type="button">重命名</button>
                        <button className={styles.sessionMenuItemDanger} disabled={deleteLoading} onClick={() => void openDeleteForSession(session)} type="button">
                          {deleteLoading && currentSessionId === session.id ? "删除中..." : "删除"}
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
              {!filteredSessions.length ? <p className={styles.emptyState}>没有匹配的会话</p> : null}
            </div>
          </div>

          <div className={styles.sidebarFooter}>
            <div className={styles.userInfo}>
              <strong>{currentUser?.username || "当前用户"}</strong>
              <span>{currentUser?.role === "admin" ? "管理员" : "普通用户"}</span>
            </div>
            <button className={styles.sidebarLogout} onClick={handleLogout} type="button">退出</button>
          </div>
        </aside>

        {/* ===== Header ===== */}
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <div>
              <p className={styles.contentEyebrow}>首页 / {currentSession?.title || "新会话"}</p>
              <h2 className={styles.contentTitle}>{currentSession?.title || "新会话"}</h2>
            </div>
          </div>
          <div className={styles.headerActions}>
            <button
              className={styles.panelToggleButton}
              onClick={() => setInspectorOpen((current) => !current)}
              title={inspectorOpen ? "收起详情" : "展开详情"}
              type="button"
            >
              <span className={styles.panelToggleIcon} />
            </button>
          </div>
        </header>

        {/* ===== Workspace ===== */}
        <section className={`${styles.workspace} ${inspectorOpen ? styles.workspaceWithInspector : ""}`}>
          {renaming ? (
            <div className={styles.renameBar}>
              <input className={styles.renameInput} onChange={(event) => setRenameTitle(event.target.value)} placeholder="输入新的会话标题" value={renameTitle} />
              <button className={styles.primaryAction} disabled={renameLoading} onClick={() => void handleRenameSession()} type="button">{renameLoading ? "保存中..." : "保存"}</button>
              <button className={styles.secondaryButton} onClick={() => { setRenaming(false); setRenameTitle(currentSession?.title ?? ""); }} type="button">取消</button>
            </div>
          ) : null}

          <div className={styles.chatCanvas} ref={chatCanvasRef}>
            {bootLoading || sessionLoading ? (
              <div className={styles.emptyHero}><p className={styles.emptyState}>正在加载会话内容...</p></div>
            ) : messages.length > 0 ? (
              <div className={styles.messageList}>
                {messages.map((message, idx) => {
                  const isLastAssistant = message.role === "assistant" && idx === messages.length - 1;
                  const showLoading = isLastAssistant && loading && !message.content;
                  return (
                  <article key={message.id} className={message.role === "user" ? styles.userMessage : styles.assistantMessage}>
                    <div className={styles.messageRole}>{message.role === "user" ? "你" : "Agent"}</div>
                    {showLoading ? (
                      <p className={styles.loadingHint}>{getLoadingHint(result?.steps ?? [])}</p>
                    ) : message.role === "assistant" ? (
                      <div className={styles.messageText}><ReactMarkdown>{message.content}</ReactMarkdown></div>
                    ) : (
                      <p className={styles.messageText}>{message.content}</p>
                    )}
                  </article>
                  );
                })}
              </div>
            ) : (
              <div className={styles.emptyHero}>
                <div className={styles.heroBadge}>RAG 智能问答</div>
                <h3 className={styles.heroTitle}>把问题变成清晰答案</h3>
                <p className={styles.heroCopy}>结构化提问、知识检索与深度思考，一次对话给出可执行结果。</p>
                <div className={styles.heroQuickGrid}>
                  {starterQuestions.map((item) => (
                    <button key={item} className={styles.heroQuickCard} onClick={() => setQuestion(item)} type="button">{item}</button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className={styles.composerShell}>
            <div className={styles.composerToolbar}>
              <div className={styles.kbSelectorWrap}>
                <button aria-expanded={knowledgeBasePickerOpen} className={styles.kbSelectorButton} onClick={() => setKnowledgeBasePickerOpen((current) => !current)} type="button">
                  <span className={styles.kbSelectorLabel}>{"知识库"}</span>
                  <span className={styles.kbSelectorValue}>{selectedKnowledgeBaseSummary}</span>
                </button>
                {knowledgeBasePickerOpen ? (
                  <div className={styles.kbSelectorPopover}>
                    <div className={styles.kbPopoverHeader}>
                      <div className={styles.filterHead}>
                        <span className={styles.filterLabel}>{"知识库范围"}</span>
                        <span className={styles.filterSummary}>{selectedKnowledgeBaseSummary}</span>
                      </div>
                      <div className={styles.filterActions}>
                        <button className={styles.smallGhostButton} onClick={() => setSelectedKnowledgeBaseIds([])} type="button">{"全部"}</button>
                        <button className={styles.smallGhostButton} onClick={() => setSelectedKnowledgeBaseIds(knowledgeBases.map((item) => item.id))} type="button">{"全选"}</button>
                      </div>
                    </div>
                    <div className={styles.kbPills}>
                      {knowledgeBases.map((item) => {
                        const checked = selectedKnowledgeBaseIds.includes(item.id);
                        return (
                          <label className={checked ? styles.kbPillActive : styles.kbPill} key={item.id}>
                            <input checked={checked} onChange={() => toggleKnowledgeBaseSelection(item.id)} type="checkbox" />
                            <span>{item.name}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            <form className={styles.composerForm} onSubmit={handleSubmit}>
              <textarea
                className={styles.composerInput}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    const form = event.currentTarget.closest("form");
                    if (form) form.requestSubmit();
                  }
                }}
                placeholder="输入你的问题... (Enter 发送，Shift+Enter 换行)"
                rows={2}
                value={question}
              />
              <div className={styles.composerFooter}>
                <div className={styles.composerMeta}>
                  <label className={styles.topkLabel} htmlFor="top-k">检索片段数</label>
                  <input id="top-k" className={styles.range} max={8} min={1} onChange={(event) => setTopK(Number(event.target.value))} type="range" value={topK} />
                  <span className={styles.topkValue}>{topK}</span>
                </div>
                {loading ? (
                  <button className={styles.sendButton} style={{ background: "var(--danger)" }} onClick={() => abortController?.abort()} type="button">停止</button>
                ) : (
                  <button className={styles.sendButton} disabled={bootLoading || sessionLoading} type="submit">发送</button>
                )}
              </div>
            </form>
            {error ? <p className={styles.error}>{error}</p> : null}
          </div>
        </section>
      </div>

      {/* ===== Detail panel (overlay) ===== */}
      {inspectorOpen ? (
        <aside className={styles.detailOverlay}>
          <div className={styles.detailHeader}>
            <div>
              <h3 className={styles.detailTitle}>详细信息</h3>
              <p className={styles.detailSubtitle}>执行链路、改写结果与检索来源</p>
            </div>
          </div>
          <div className={styles.statusRow}>
            <StatusBadge label="Route" value={result?.route || "-"} />
            <StatusBadge label="Retrieval" value={result?.retrieval_quality || "-"} />
            <StatusBadge label="Sources" value={String(result?.sources.length ?? 0)} />
          </div>
          <section className={styles.detailCard}>
            <h4 className={styles.detailCardTitle}>执行步骤</h4>
            {result?.steps.length ? (
              <ol className={styles.stepsList}>
                {result.steps.map((step) => (<li className={styles.stepItem} key={step}><span className={styles.stepDot} /><code>{step}</code></li>))}
              </ol>
            ) : (<p className={styles.emptyState}>还没有执行路径。</p>)}
          </section>
          <section className={styles.detailCard}>
            <h4 className={styles.detailCardTitle}>上下文补全问题</h4>
            {result?.standalone_question ? (
              <p className={styles.rewrittenQuestion}>{result.standalone_question}</p>
            ) : (<p className={styles.emptyState}>本次没有生成上下文补全问题。</p>)}
          </section>
          <section className={styles.detailCard}>
            <h4 className={styles.detailCardTitle}>改写问题</h4>
            {result?.rewritten_question ? (
              <p className={styles.rewrittenQuestion}>{result.rewritten_question}</p>
            ) : (<p className={styles.emptyState}>本次没有触发问题改写。</p>)}
          </section>
          <section className={styles.detailCard}>
            <h4 className={styles.detailCardTitle}>检索来源</h4>
            {result?.sources.length ? (
              <div>
                {result.sources.map((source, index) => (
                  <article className={styles.sourceCard} key={`${source.source}-${index}`} style={{ marginBottom: 8 }}>
                    <div className={styles.sourceMeta}>
                      <span className={styles.sourcePath}>{source.source || "未知来源"}</span>
                      <span className={styles.sourceMetaActions}>
                        <RetrievalTypeBadge type={source.retrieval_type} />
                      </span>
                    </div>
                    <div className={styles.sourceScoreGrid}>
                      <ScoreItem label="最终分" value={source.rerank_score ?? source.score} />
                      <ScoreItem label="向量分" value={source.vector_score} />
                      <ScoreItem label="关键词分" value={source.keyword_score} />
                    </div>
                    <p className={styles.sourceContent}>{source.content}</p>
                  </article>
                ))}
              </div>
            ) : (<p className={styles.emptyState}>本次没有返回知识库检索片段。</p>)}
          </section>
        </aside>
      ) : null}
    </main>
  );
}

function StatusBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className={styles.badge}>
      <span className={styles.badgeLabel}>{label}</span>
      <span className={styles.badgeValue}>{value}</span>
    </span>
  );
}

function formatScore(value?: number | null) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function ScoreItem({ label, value }: { label: string; value?: number | null }) {
  return (
    <span className={styles.sourceScoreItem}>
      <span className={styles.sourceScoreLabel}>{label}</span>
      <span className={styles.sourceScoreValue}>{formatScore(value)}</span>
    </span>
  );
}

const STEP_LABELS: Record<string, string> = {
  complete: "正在补全上下文...",
  analyze: "正在分析问题...",
  retrieve: "正在检索知识库...",
  check: "正在检查相关性...",
  rewrite: "正在改写问题...",
  generate: "正在生成回答...",
};

function getLoadingHint(steps: string[]): string {
  if (steps.length === 0) return "正在思考...";
  const last = steps[steps.length - 1];
  const key = Object.keys(STEP_LABELS).find((item) => last.includes(item));
  return key ? STEP_LABELS[key] : `正在执行 ${last}...`;
}

const RETRIEVAL_TYPE_MAP: Record<string, { label: string; className: string }> = {
  vector: { label: "向量", className: styles.retrievalTypeVector },
  keyword: { label: "关键词", className: styles.retrievalTypeKeyword },
  hybrid: { label: "混合", className: styles.retrievalTypeHybrid },
};

function RetrievalTypeBadge({ type }: { type?: string | null }) {
  const meta = RETRIEVAL_TYPE_MAP[type || ""];
  if (!meta) return null;
  return (
    <span className={`${styles.retrievalTypeBadge} ${meta.className}`}>
      {meta.label}
    </span>
  );
}
