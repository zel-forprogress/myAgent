"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { MenuIcon } from "../components/MenuIcon";
import { chat, common } from "./messages";
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
  chat.starter[0],
  chat.starter[1],
  chat.starter[2],
];

type StreamEvent = {
  type: string;
  data: Record<string, unknown>;
};

function emptyChatResult(answer = ""): ChatResponse {
  return {
    answer,
    sources: [],
    route: "",
    task_intent: "",
    task_confidence: 0,
    agent_plan: [],
    tool_calls: [],
    steps: [],
    retrieval_quality: "",
    rewritten_question: "",
    standalone_question: "",
  };
}

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
    if (selectedKnowledgeBaseIds.length === 0) return chat.composer.allKb;
    if (selectedKnowledgeBases.length === 0) return chat.composer.noMatchKb;
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
    return { id, session_id: currentSessionId, role, content, route: "", task_intent: "", task_confidence: 0, agent_plan: [], tool_calls: [], retrieval_quality: "", rewritten_question: "", standalone_question: "", source_count: 0, sources: [], steps: [], created_at: new Date().toISOString() };
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
      handleAuthAwareError(bootstrapError, chat.error.bootstrap);
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
    if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : chat.api.fetchKbFailed);
    return payload as KnowledgeBaseResponse[];
  }

  async function fetchSessions() {
    const response = await authFetch(`${apiBaseUrl}/sessions`);
    const payload = (await response.json()) as SessionListResponse | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : chat.api.fetchSessionsFailed);
    return (payload as SessionListResponse).sessions;
  }

  async function createSession() {
    const response = await authFetch(`${apiBaseUrl}/sessions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "" }) });
    const payload = (await response.json()) as SessionResponse | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : chat.api.createSessionFailed);
    return payload as SessionResponse;
  }

  async function fetchSessionMessages(sessionId: string) {
    const response = await authFetch(`${apiBaseUrl}/sessions/${sessionId}/messages`);
    const payload = (await response.json()) as SessionMessagesResponse | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : chat.api.fetchMessagesFailed);
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
        setResult({ answer: latestAssistant.content, sources: latestAssistant.sources, route: latestAssistant.route, task_intent: latestAssistant.task_intent, task_confidence: latestAssistant.task_confidence, agent_plan: latestAssistant.agent_plan, tool_calls: latestAssistant.tool_calls, steps: latestAssistant.steps, retrieval_quality: latestAssistant.retrieval_quality, rewritten_question: latestAssistant.rewritten_question, standalone_question: latestAssistant.standalone_question });
      } else {
        setResult(null);
      }
    } catch (selectError) {
      handleAuthAwareError(selectError, chat.api.switchSessionFailed);
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
      handleAuthAwareError(createError, chat.api.newSessionFailed);
    }
  }

  async function handleRenameSession(sessionId: string = currentSessionId) {
    const trimmedTitle = renameTitle.trim();
    if (!sessionId || !trimmedTitle) { setError(chat.session.renameTitle); return; }
    setRenameLoading(true);
    setError("");
    try {
      const response = await authFetch(`${apiBaseUrl}/sessions/${sessionId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: trimmedTitle }) });
      const payload = (await response.json()) as SessionResponse | { detail?: string };
      if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : chat.api.renameSessionFailed);
      const updated = payload as SessionResponse;
      setSessions((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      if (updated.id === currentSessionId) setRenameTitle(updated.title);
      setRenaming(false);
      setMenuSessionId("");
    } catch (renameError) {
      handleAuthAwareError(renameError, chat.api.renameSessionFailed);
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
      if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : chat.api.deleteSessionFailed);
      const nextSessions = sessions.filter((item) => item.id !== sessionId);
      setSessions(nextSessions);
      setMenuSessionId("");
      if (sessionId === currentSessionId) {
        if (nextSessions.length > 0) { await selectSession(nextSessions[0].id, nextSessions); }
        else { const created = await createSession(); setSessions([created]); await selectSession(created.id, [created]); }
      }
    } catch (deleteError) {
      handleAuthAwareError(deleteError, chat.api.deleteSessionFailed);
    } finally {
      setDeleteLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;
    if (!currentSessionId) { setError(chat.error.noSession); return; }
    isUserScrolledUpRef.current = false;
    setLoading(true);
    setError("");
    try {
      const auth = getStoredAuth();
      if (!auth?.token) throw new AuthError(chat.error.authExpired);
      const tempUserId = Date.now();
      const tempAssistantId = tempUserId + 1;
      const userMessage = buildTempMessage(tempUserId, "user", trimmedQuestion);
      const assistantMessage = buildTempMessage(tempAssistantId, "assistant", "");
      setMessages((current) => [...current, userMessage, assistantMessage]);
      setResult(emptyChatResult());
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
            setResult((current) => {
              const base = current ?? emptyChatResult(answerBuffer);
              const nextPlan = Array.isArray(eventPayload.data.agent_plan)
                ? (eventPayload.data.agent_plan as string[])
                : base.agent_plan;
              const nextToolCalls = Array.isArray(eventPayload.data.tool_calls)
                ? (eventPayload.data.tool_calls as ChatResponse["tool_calls"])
                : base.tool_calls;
              return {
                ...base,
                answer: answerBuffer,
                route: String(eventPayload.data.route ?? "") || base.route,
                task_intent: String(eventPayload.data.task_intent ?? "") || base.task_intent,
                task_confidence: Number(eventPayload.data.task_confidence ?? base.task_confidence) || base.task_confidence,
                agent_plan: nextPlan,
                tool_calls: nextToolCalls,
                retrieval_quality: String(eventPayload.data.retrieval_quality ?? "") || base.retrieval_quality,
                steps: step && !base.steps.includes(step) ? [...base.steps, step] : base.steps,
              };
            });
          } else if (eventPayload.type === "sources") {
            const nextSources = Array.isArray(eventPayload.data.sources) ? (eventPayload.data.sources as ChatResponse["sources"]) : [];
            setResult((current) => { const base = current ?? emptyChatResult(answerBuffer); return { ...base, answer: answerBuffer, sources: nextSources }; });
          } else if (eventPayload.type === "meta") {
            setResult((current) => {
              const base = current ?? emptyChatResult(answerBuffer);
              return {
                ...base,
                answer: answerBuffer,
                agent_plan: Array.isArray(eventPayload.data.agent_plan)
                  ? (eventPayload.data.agent_plan as string[])
                  : base.agent_plan,
                tool_calls: Array.isArray(eventPayload.data.tool_calls)
                  ? (eventPayload.data.tool_calls as ChatResponse["tool_calls"])
                  : base.tool_calls,
                rewritten_question: String(eventPayload.data.rewritten_question ?? "") || base.rewritten_question,
                standalone_question: String(eventPayload.data.standalone_question ?? "") || base.standalone_question,
              };
            });
          } else if (eventPayload.type === "token") {
            const content = String(eventPayload.data.content ?? "");
            if (!content) continue;
            answerBuffer += content;
            updateTempAssistantMessage(tempAssistantId, answerBuffer);
            setResult((current) => { const base = current ?? emptyChatResult(); return { ...base, answer: answerBuffer }; });
          } else if (eventPayload.type === "final") {
            const finalPayload = eventPayload.data as unknown as ChatResponse;
            answerBuffer = finalPayload.answer;
            updateTempAssistantMessage(tempAssistantId, finalPayload.answer);
            setResult(finalPayload);
          } else if (eventPayload.type === "error") {
            throw new Error(String(eventPayload.data.message ?? chat.error.streamFailed));
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
        handleAuthAwareError(submitError, chat.error.requestFailed);
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

          <p className={styles.navLabel}>{chat.nav.label}</p>
          <div className={styles.menuList}>
            <button
              className={styles.menuItem}
              onClick={() => void handleCreateSession()}
              type="button"
            >
              <span className={styles.menuIcon}><MenuIcon variant="chat" /></span>
              {chat.nav.newChat}
            </button>
            {currentUser?.role === "admin" ? (
              <Link className={styles.menuItem} href="/admin">
                <span className={styles.menuIcon}><MenuIcon variant="grid" /></span>
                {chat.nav.admin}
              </Link>
            ) : null}
          </div>

          <div className={styles.searchCard}>
            <input
              className={styles.searchInput}
              onChange={(event) => setSessionKeyword(event.target.value)}
              placeholder={chat.search.placeholder}
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
                      <span className={styles.sessionMeta}>{session.message_count} {chat.session.messages}</span>
                    </button>
                    <button
                      className={menuOpen ? styles.sessionMenuButtonActive : styles.sessionMenuButton}
                      onClick={() => setMenuSessionId((current) => (current === session.id ? "" : session.id))}
                      type="button"
                    >...</button>
                    {menuOpen ? (
                      <div className={styles.sessionMenu}>
                        <button className={styles.sessionMenuItem} onClick={() => void openRenameForSession(session)} type="button">{common.rename}</button>
                        <button className={styles.sessionMenuItemDanger} disabled={deleteLoading} onClick={() => void openDeleteForSession(session)} type="button">
                          {deleteLoading && currentSessionId === session.id ? chat.session.deleting : common.delete}
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
              {!filteredSessions.length ? <p className={styles.emptyState}>{chat.search.noMatch}</p> : null}
            </div>
          </div>

          <div className={styles.sidebarFooter}>
            <div className={styles.userInfo}>
              <strong>{currentUser?.username || common.unknown}</strong>
              <span>{currentUser?.role === "admin" ? chat.user.admin : chat.user.regular}</span>
            </div>
            <button className={styles.sidebarLogout} onClick={handleLogout} type="button">{chat.user.logout}</button>
          </div>
        </aside>

        {/* ===== Header ===== */}
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <div>
              <p className={styles.contentEyebrow}>{chat.header.home} / {currentSession?.title || chat.header.newSession}</p>
              <h2 className={styles.contentTitle}>{currentSession?.title || chat.header.newSession}</h2>
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
              <input className={styles.renameInput} onChange={(event) => setRenameTitle(event.target.value)} placeholder={chat.session.renamePlaceholder} value={renameTitle} />
              <button className={styles.primaryAction} disabled={renameLoading} onClick={() => void handleRenameSession()} type="button">{renameLoading ? common.saving : common.save}</button>
              <button className={styles.secondaryButton} onClick={() => { setRenaming(false); setRenameTitle(currentSession?.title ?? ""); }} type="button">{common.cancel}</button>
            </div>
          ) : null}

          <div className={styles.chatCanvas} ref={chatCanvasRef}>
            {bootLoading || sessionLoading ? (
              <div className={styles.emptyHero}><p className={styles.emptyState}>{chat.empty.loading}</p></div>
            ) : messages.length > 0 ? (
              <div className={styles.messageList}>
                {messages.map((message, idx) => {
                  const isLastAssistant = message.role === "assistant" && idx === messages.length - 1;
                  const showLoading = isLastAssistant && loading && !message.content;
                  return (
                    <article key={message.id} className={message.role === "user" ? styles.userMessage : styles.assistantMessage}>
                      <div className={styles.messageRole}>{message.role === "user" ? chat.role.user : chat.role.assistant}</div>
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
                <div className={styles.heroBadge}>{chat.empty.hero.badge}</div>
                <h3 className={styles.heroTitle}>{chat.empty.hero.title}</h3>
                <p className={styles.heroCopy}>{chat.empty.hero.copy}</p>
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
                  <span className={styles.kbSelectorLabel}>{chat.composer.knowledgeBase}</span>
                  <span className={styles.kbSelectorValue}>{selectedKnowledgeBaseSummary}</span>
                </button>
                {knowledgeBasePickerOpen ? (
                  <div className={styles.kbSelectorPopover}>
                    <div className={styles.kbPopoverHeader}>
                      <div className={styles.filterHead}>
                        <span className={styles.filterLabel}>{chat.composer.knowledgeBase}</span>
                        <span className={styles.filterSummary}>{selectedKnowledgeBaseSummary}</span>
                      </div>
                      <div className={styles.filterActions}>
                        <button className={styles.smallGhostButton} onClick={() => setSelectedKnowledgeBaseIds([])} type="button">全部</button>
                        <button className={styles.smallGhostButton} onClick={() => setSelectedKnowledgeBaseIds(knowledgeBases.map((item) => item.id))} type="button">全选</button>
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
                placeholder={chat.composer.placeholder}
                rows={2}
                value={question}
              />
              <div className={styles.composerFooter}>
                <div className={styles.composerMeta}>
                  <label className={styles.topkLabel} htmlFor="top-k">{chat.composer.topK}</label>
                  <input id="top-k" className={styles.range} max={8} min={1} onChange={(event) => setTopK(Number(event.target.value))} type="range" value={topK} />
                  <span className={styles.topkValue}>{topK}</span>
                </div>
                {loading ? (
                  <button className={styles.sendButton} style={{ background: "var(--danger)" }} onClick={() => abortController?.abort()} type="button">{chat.composer.stop}</button>
                ) : (
                  <button className={styles.sendButton} disabled={bootLoading || sessionLoading} type="submit">{chat.composer.send}</button>
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
            <StatusBadge label="Intent" value={formatTaskIntent(result?.task_intent)} />
            <StatusBadge label="Retrieval" value={result?.retrieval_quality || "-"} />
            <StatusBadge label="Sources" value={String(result?.sources.length ?? 0)} />
          </div>
          <section className={styles.detailCard}>
            <h4 className={styles.detailCardTitle}>Agent 计划</h4>
            {result?.agent_plan.length ? (
              <ol className={styles.stepsList}>
                {result.agent_plan.map((item, index) => (
                  <li className={styles.stepItem} key={`${item}-${index}`}>
                    <span className={styles.stepDot} />
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            ) : (<p className={styles.emptyState}>本次还没有生成 Agent 计划。</p>)}
          </section>
          <section className={styles.detailCard}>
            <h4 className={styles.detailCardTitle}>工具调用</h4>
            {result?.tool_calls.length ? (
              <div className={styles.stepsList}>
                {result.tool_calls.map((toolCall, index) => (
                  <article className={styles.toolCallCard} key={`${toolCall.name}-${index}`}>
                    <div className={styles.toolCallHeader}>
                      <code>{formatToolName(toolCall.name)}</code>
                      <span>{toolCall.status || "success"}</span>
                    </div>
                    <p className={styles.toolCallPayload}>
                      {formatToolPayload(toolCall.output || toolCall.input)}
                    </p>
                  </article>
                ))}
              </div>
            ) : (<p className={styles.emptyState}>本次还没有工具调用记录。</p>)}
          </section>
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
                      <span className={styles.sourcePath}>{source.source || common.unknownSource}</span>
                      <span className={styles.sourceMetaActions}>
                        <RetrievalTypeBadge
                          rerankScore={source.rerank_score}
                          type={source.retrieval_type}
                        />
                      </span>
                    </div>
                    <div className={styles.sourceScoreGrid}>
                      <ScoreItem label="最终分" value={source.score} />
                      <ScoreItem label="Rerank 分" value={source.rerank_score} />
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

function formatTaskIntent(intent?: string | null) {
  return (
    {
      chat: "闲聊",
      knowledge_qa: "知识问答",
      summarize: "总结",
      compare: "对比",
      extract: "抽取",
      write: "写作",
      tool: "工具",
    }[intent || ""] || intent || "-"
  );
}

const TOOL_NAME_MAP: Record<string, string> = {
  agent_planner: "\u4efb\u52a1\u89c4\u5212",
  search_knowledge_base: "\u77e5\u8bc6\u5e93\u68c0\u7d22",
  inspect_sources: "\u6765\u6e90\u8bca\u65ad",
  guard_no_context: "\u65e0\u8d44\u6599\u4fdd\u62a4",
  query_rewriter: "\u95ee\u9898\u6539\u5199",
  answer_generator: "\u7b54\u6848\u751f\u6210",
  direct_answer_generator: "\u76f4\u63a5\u56de\u7b54",
};

function formatToolName(name: string) {
  return TOOL_NAME_MAP[name] || name;
}

function formatToolPayload(payload?: Record<string, unknown>) {
  if (!payload || Object.keys(payload).length === 0) {
    return "-";
  }
  const compactKeys = [
    "source_count",
    "candidate_count",
    "max_score",
    "retrieval_quality",
    "reason",
    "recommendation",
    "rerank_enabled",
    "rerank_applied",
    "answer_length",
  ];
  const compact = compactKeys
    .filter((key) => payload[key] !== undefined)
    .map((key) => `${key}: ${String(payload[key])}`);
  if (compact.length > 0) {
    return compact.join(" | ");
  }
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
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
  complete: chat.loading.complete,
  analyze: chat.loading.analyze,
  retrieve: chat.loading.retrieve,
  check: chat.loading.check,
  rewrite: chat.loading.rewrite,
  generate: chat.loading.generate,
};

function getLoadingHint(steps: string[]): string {
  if (steps.length === 0) return chat.loading.thinking;
  const last = steps[steps.length - 1];
  const key = Object.keys(STEP_LABELS).find((item) => last.includes(item));
  return key ? STEP_LABELS[key] : `正在执行 ${last}...`;
}

const RETRIEVAL_TYPE_MAP: Record<string, { label: string; className: string }> = {
  vector: { label: "向量", className: styles.retrievalTypeVector },
  keyword: { label: "关键词", className: styles.retrievalTypeKeyword },
  hybrid: { label: "混合", className: styles.retrievalTypeHybrid },
};

function RetrievalTypeBadge({
  rerankScore,
  type,
}: {
  rerankScore?: number | null;
  type?: string | null;
}) {
  if (typeof rerankScore === "number") {
    return (
      <span className={`${styles.retrievalTypeBadge} ${styles.retrievalTypeRerank}`}>
        已重排
      </span>
    );
  }
  const meta = RETRIEVAL_TYPE_MAP[type || ""];
  if (!meta) return null;
  return (
    <span className={`${styles.retrievalTypeBadge} ${meta.className}`}>
      {meta.label}
    </span>
  );
}
