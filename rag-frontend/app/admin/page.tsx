"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { MenuIcon, type MenuIconVariant } from "../../components/MenuIcon";
import { Pagination } from "../../components/Pagination";
import styles from "./page.module.css";
import {
  apiBaseUrl,
  DeleteDocumentResponse,
  DeleteKnowledgeBaseResponse,
  DeleteSessionResponse,
  DocumentInfo,
  DocumentsResponse,
  IngestResponse,
  KnowledgeBaseResponse,
  MessageResponse,
  SessionListResponse,
  SessionMessagesResponse,
  SessionResponse,
  UserResponse,
} from "../../lib/api";
import {
  AuthError,
  authFetch,
  clearStoredAuth,
  fetchCurrentUser,
  getStoredAuth,
} from "../../lib/auth";

type HealthResponse = {
  status: string;
};

type Notice = {
  type: "success" | "error";
  text: string;
};

type DocumentSearchResult = {
  document: DocumentInfo;
  knowledgeBase: KnowledgeBaseResponse;
};

const KNOWLEDGE_BASE_PAGE_SIZE = 6;

type AdminView =
  | "overview"
  | "knowledge-bases"
  | "sessions"
  | "users";

type MenuItem = {
  key: AdminView;
  label: string;
  description: string;
  icon: ReactNode;
};

const adminMenus: MenuItem[] = [
  {
    key: "overview",
    label: "系统概览",
    description: "查看服务状态和整体业务统计",
    icon: <MenuIcon variant="grid" />,
  },
  {
    key: "knowledge-bases",
    label: "知识库管理",
    description: "创建、切换、删除知识库",
    icon: <MenuIcon variant="layers" />,
  },
  {
    key: "sessions",
    label: "聊天会话",
    description: "查看所有用户会话和绑定知识库",
    icon: <MenuIcon variant="chat" />,
  },
  {
    key: "users",
    label: "用户管理",
    description: "创建、查看、删除用户",
    icon: <MenuIcon variant="people" />,
  },
];

export default function AdminPage() {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [activeView, setActiveView] = useState<AdminView>("knowledge-bases");
  const [knowledgeBaseDetailOpen, setKnowledgeBaseDetailOpen] = useState(false);
  const [health, setHealth] = useState("checking");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseResponse[]>([]);
  const [documentCounts, setDocumentCounts] = useState<Record<string, number>>({});
  const [knowledgeBaseQuery, setKnowledgeBaseQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchDocuments, setSearchDocuments] = useState<DocumentSearchResult[]>([]);
  const [focusedKnowledgeBaseId, setFocusedKnowledgeBaseId] = useState("");
  const [focusedDocumentSource, setFocusedDocumentSource] = useState("");
  const [knowledgeBasePage, setKnowledgeBasePage] = useState(1);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [collection, setCollection] = useState("");
  const [docError, setDocError] = useState("");
  const [docLoading, setDocLoading] = useState(false);
  const [docPage, setDocPage] = useState(1);
  const [docTotal, setDocTotal] = useState(0);
  const DOC_PAGE_SIZE = 15;
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [sessionPage, setSessionPage] = useState(1);
  const [sessionTotal, setSessionTotal] = useState(0);
  const SESSION_PAGE_SIZE = 15;
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [sessionMessages, setSessionMessages] = useState<MessageResponse[]>([]);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionNotice, setSessionNotice] = useState<Notice | null>(null);
  const [deletingSessionId, setDeletingSessionId] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadNotice, setUploadNotice] = useState<Notice | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [deleteNotice, setDeleteNotice] = useState<Notice | null>(null);
  const [deletingSource, setDeletingSource] = useState("");
  const [newKnowledgeBaseName, setNewKnowledgeBaseName] = useState("");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [newEmbeddingModel, setNewEmbeddingModel] = useState("");
  const [createKnowledgeBaseOpen, setCreateKnowledgeBaseOpen] = useState(false);
  const [knowledgeBaseNotice, setKnowledgeBaseNotice] = useState<Notice | null>(null);
  const [creatingKnowledgeBase, setCreatingKnowledgeBase] = useState(false);
  const [deletingKnowledgeBaseId, setDeletingKnowledgeBaseId] = useState("");

  // --- User management ---
  type UserListItem = { id: string; username: string; role: string; created_at: string };
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [userTotal, setUserTotal] = useState(0);
  const [userNotice, setUserNotice] = useState<Notice | null>(null);
  const [creatingUser, setCreatingUser] = useState(false);
  const [deletingUserId, setDeletingUserId] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [userPage, setUserPage] = useState(1);
  const USER_PAGE_SIZE = 15;

  const selectedKnowledgeBase = useMemo(
    () =>
      knowledgeBases.find((item) => item.id === selectedKnowledgeBaseId) ??
      knowledgeBases[0] ??
      null,
    [knowledgeBases, selectedKnowledgeBaseId],
  );

  const selectedSession = useMemo(
    () => sessions.find((item) => item.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  );

  const matchingKnowledgeBases = useMemo(() => {
    const query = knowledgeBaseQuery.trim().toLocaleLowerCase();
    if (!query) {
      return [];
    }
    return knowledgeBases.filter((item) =>
      [item.name, item.slug, item.collection_name].some((value) =>
        value.toLocaleLowerCase().includes(query),
      ),
    );
  }, [knowledgeBaseQuery, knowledgeBases]);

  const visibleKnowledgeBases = useMemo(
    () =>
      focusedKnowledgeBaseId
        ? knowledgeBases.filter((item) => item.id === focusedKnowledgeBaseId)
        : knowledgeBases,
    [focusedKnowledgeBaseId, knowledgeBases],
  );

  const visibleDocuments = useMemo(
    () =>
      focusedDocumentSource
        ? documents.filter((item) => item.source === focusedDocumentSource)
        : documents,
    [documents, focusedDocumentSource],
  );

  const knowledgeBasePageCount = Math.max(
    1,
    Math.ceil(visibleKnowledgeBases.length / KNOWLEDGE_BASE_PAGE_SIZE),
  );
  const safeKnowledgeBasePage = Math.min(knowledgeBasePage, knowledgeBasePageCount);
  const paginatedKnowledgeBases = useMemo(() => {
    const start = (safeKnowledgeBasePage - 1) * KNOWLEDGE_BASE_PAGE_SIZE;
    return visibleKnowledgeBases.slice(start, start + KNOWLEDGE_BASE_PAGE_SIZE);
  }, [safeKnowledgeBasePage, visibleKnowledgeBases]);

  const totalDocumentCount = useMemo(
    () => Object.values(documentCounts).reduce((total, count) => total + count, 0),
    [documentCounts],
  );

  const knowledgeBasesWithDocuments = useMemo(
    () => Object.values(documentCounts).filter((count) => count > 0).length,
    [documentCounts],
  );

  const conversationUserCount = useMemo(
    () =>
      new Set(
        sessions
          .map((session) => session.owner_username)
          .filter((username): username is string => Boolean(username)),
      ).size,
    [sessions],
  );

  const activeMenu = useMemo(
    () => adminMenus.find((item) => item.key === activeView) ?? adminMenus[0],
    [activeView],
  );

  useEffect(() => {
    void bootstrapAdmin();
  }, []);

  useEffect(() => {
    if (authReady && selectedKnowledgeBaseId) {
      void loadDocuments(selectedKnowledgeBaseId);
    }
  }, [authReady, selectedKnowledgeBaseId, docPage]);

  useEffect(() => {
    const query = knowledgeBaseQuery.trim().toLocaleLowerCase();
    if (!authReady || !query) {
      setSearchDocuments([]);
      setSearchLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setSearchLoading(true);
      try {
        const results = await Promise.all(
          knowledgeBases.map(async (knowledgeBase) => {
            const response = await authFetch(
              `${apiBaseUrl}/documents?knowledge_base_id=${encodeURIComponent(knowledgeBase.id)}`,
            );
            if (!response.ok) {
              return [];
            }
            const payload = (await response.json()) as DocumentsResponse;
            return payload.documents
              .filter((document) =>
                [document.filename, document.source].some((value) =>
                  value.toLocaleLowerCase().includes(query),
                ),
              )
              .map((document) => ({ document, knowledgeBase }));
          }),
        );
        if (!cancelled) {
          setSearchDocuments(results.flat());
        }
      } catch {
        if (!cancelled) {
          setSearchDocuments([]);
        }
      } finally {
        if (!cancelled) {
          setSearchLoading(false);
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [authReady, knowledgeBaseQuery, knowledgeBases]);

  useEffect(() => {
    setKnowledgeBasePage((page) => Math.min(page, knowledgeBasePageCount));
  }, [knowledgeBasePageCount]);

  async function bootstrapAdmin() {
    try {
      const auth = getStoredAuth();
      if (!auth) {
        router.replace("/login");
        return;
      }

      const user = await fetchCurrentUser();
      if (user.role !== "admin") {
        router.replace("/");
        return;
      }

      setCurrentUser(user);

      const [knowledgeBaseList, sessionList] = await Promise.all([
        fetchKnowledgeBases(),
        fetchSessions(),
      ]);

      setKnowledgeBases(knowledgeBaseList);
      if (knowledgeBaseList.length > 0) {
        setSelectedKnowledgeBaseId(knowledgeBaseList[0].id);
      }

      setSessions(sessionList);
      if (sessionList.length > 0) {
        await loadSessionMessages(sessionList[0].id);
      }

      await Promise.all([loadHealth(), loadDocumentCounts(knowledgeBaseList)]);
      try { await fetchUsers(userPage, USER_PAGE_SIZE); } catch { /* users tab will load on demand */ }
      setAuthReady(true);
    } catch (error) {
      handleAuthAwareError(error, "初始化后台失败。");
    }
  }

  function handleAuthAwareError(errorValue: unknown, fallbackMessage: string) {
    if (errorValue instanceof AuthError) {
      clearStoredAuth();
      router.replace("/login");
      return;
    }

    if (errorValue instanceof Error && errorValue.message.includes("Admin permission")) {
      router.replace("/");
      return;
    }

    setDocError(errorValue instanceof Error ? errorValue.message : fallbackMessage);
  }

  async function loadHealth() {
    try {
      const response = await fetch(`${apiBaseUrl}/health`);
      const payload = (await response.json()) as HealthResponse;
      setHealth(payload.status || "unknown");
    } catch {
      setHealth("error");
    }
  }

  async function fetchKnowledgeBases() {
    const response = await authFetch(`${apiBaseUrl}/knowledge-bases`);
    const payload = (await response.json()) as
      | KnowledgeBaseResponse[]
      | { detail?: string };

    if (!response.ok) {
      throw new Error(
        "detail" in payload && typeof payload.detail === "string"
          ? payload.detail
          : "获取知识库列表失败。",
      );
    }

    return payload as KnowledgeBaseResponse[];
  }

  async function fetchSessions(page = 1, pageSize = SESSION_PAGE_SIZE) {
    const response = await authFetch(
      `${apiBaseUrl}/sessions?page=${page}&page_size=${pageSize}`,
    );
    const payload = (await response.json()) as
      | SessionListResponse
      | { detail?: string };

    if (!response.ok) {
      throw new Error(
        "detail" in payload && typeof payload.detail === "string"
          ? payload.detail
          : "获取会话列表失败。",
      );
    }

    const data = payload as SessionListResponse;
    setSessionTotal(data.total || 0);
    return data.sessions;
  }

  async function loadDocuments(knowledgeBaseId: string) {
    setDocLoading(true);
    setDocError("");

    try {
      const response = await authFetch(
        `${apiBaseUrl}/documents?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}&page=${docPage}&page_size=${DOC_PAGE_SIZE}`,
      );
      const payload = (await response.json()) as
        | DocumentsResponse
        | { detail?: string };

      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "获取文档列表失败。",
        );
      }

      const successPayload = payload as DocumentsResponse;
      setCollection(successPayload.collection);
      setDocuments(successPayload.documents);
      setDocTotal(successPayload.total || 0);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "获取文档列表失败。");
        return;
      }
      setDocError(error instanceof Error ? error.message : "获取文档列表失败。");
    } finally {
      setDocLoading(false);
    }
  }

  async function loadDocumentCounts(knowledgeBaseList: KnowledgeBaseResponse[]) {
    const entries = await Promise.all(
      knowledgeBaseList.map(async (knowledgeBase) => {
        try {
          const response = await authFetch(
            `${apiBaseUrl}/documents?knowledge_base_id=${encodeURIComponent(knowledgeBase.id)}`,
          );
          if (!response.ok) {
            return [knowledgeBase.id, 0] as const;
          }
          const payload = (await response.json()) as DocumentsResponse;
          return [knowledgeBase.id, payload.documents.length] as const;
        } catch {
          return [knowledgeBase.id, 0] as const;
        }
      }),
    );
    setDocumentCounts(Object.fromEntries(entries));
  }

  async function loadSessionMessages(sessionId: string) {
    setSelectedSessionId(sessionId);

    const response = await authFetch(`${apiBaseUrl}/sessions/${sessionId}/messages`);
    const payload = (await response.json()) as
      | SessionMessagesResponse
      | { detail?: string };

    if (!response.ok) {
      throw new Error(
        "detail" in payload && typeof payload.detail === "string"
          ? payload.detail
          : "获取会话消息失败。",
      );
    }

    const successPayload = payload as SessionMessagesResponse;
    setSessionMessages(successPayload.messages);
  }

  async function reloadSessions() {
    setSessionLoading(true);
    setSessionNotice(null);
    try {
      const nextSessions = await fetchSessions(sessionPage, SESSION_PAGE_SIZE);
      setSessions(nextSessions);
      if (nextSessions.length > 0) {
        const nextId =
          nextSessions.find((item) => item.id === selectedSessionId)?.id ??
          nextSessions[0].id;
        await loadSessionMessages(nextId);
      } else {
        setSelectedSessionId("");
        setSessionMessages([]);
      }
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "获取会话列表失败。");
        return;
      }
      setSessionNotice({
        type: "error",
        text: error instanceof Error ? error.message : "获取会话列表失败。",
      });
    } finally {
      setSessionLoading(false);
    }
  }

  async function reloadKnowledgeBases(preferredKnowledgeBaseId?: string) {
    const nextKnowledgeBases = await fetchKnowledgeBases();
    setKnowledgeBases(nextKnowledgeBases);
    await loadDocumentCounts(nextKnowledgeBases);

    const nextSelectedId =
      preferredKnowledgeBaseId &&
      nextKnowledgeBases.some((item) => item.id === preferredKnowledgeBaseId)
        ? preferredKnowledgeBaseId
        : nextKnowledgeBases[0]?.id || "";

    setSelectedKnowledgeBaseId(nextSelectedId);
  }

  async function handleCreateKnowledgeBase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = newKnowledgeBaseName.trim();
    const trimmedCollection = newCollectionName.trim();
    const trimmedEmbedding = newEmbeddingModel.trim();
    if (!trimmedName || !trimmedCollection || !trimmedEmbedding) {
      setKnowledgeBaseNotice({ type: "error", text: "请填写所有必填字段。" });
      return;
    }
    if (!/^[a-z0-9][a-z0-9_]*$/.test(trimmedCollection)) {
      setKnowledgeBaseNotice({ type: "error", text: "Collection 名称只能包含小写字母、数字和下划线。" });
      return;
    }

    setCreatingKnowledgeBase(true);
    setKnowledgeBaseNotice(null);

    try {
      const response = await authFetch(`${apiBaseUrl}/knowledge-bases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: trimmedName,
          collection_name: trimmedCollection,
          embedding_model: trimmedEmbedding,
        }),
      });
      const payload = (await response.json()) as
        | KnowledgeBaseResponse
        | { detail?: string };

      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "创建知识库失败。",
        );
      }

      const created = payload as KnowledgeBaseResponse;
      await reloadKnowledgeBases(created.id);
      setNewKnowledgeBaseName("");
      setNewCollectionName("");
      setNewEmbeddingModel("");
      setCreateKnowledgeBaseOpen(false);
      setKnowledgeBaseNotice({
        type: "success",
        text: `知识库“${created.name}”已创建。`,
      });
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "创建知识库失败。");
        return;
      }
      setKnowledgeBaseNotice({
        type: "error",
        text: error instanceof Error ? error.message : "创建知识库失败。",
      });
    } finally {
      setCreatingKnowledgeBase(false);
    }
  }

  async function handleDeleteKnowledgeBase(knowledgeBase: KnowledgeBaseResponse) {
    setDeletingKnowledgeBaseId(knowledgeBase.id);
    setKnowledgeBaseNotice(null);

    try {
      const response = await authFetch(
        `${apiBaseUrl}/knowledge-bases/${knowledgeBase.id}`,
        { method: "DELETE" },
      );
      const payload = (await response.json()) as
        | DeleteKnowledgeBaseResponse
        | { detail?: string };

      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "删除知识库失败。",
        );
      }

      const nextSelectedId =
        selectedKnowledgeBaseId === knowledgeBase.id ? undefined : selectedKnowledgeBaseId;
      await reloadKnowledgeBases(nextSelectedId);
      setKnowledgeBaseNotice({
        type: "success",
        text: (payload as DeleteKnowledgeBaseResponse).message,
      });
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "删除知识库失败。");
        return;
      }
      setKnowledgeBaseNotice({
        type: "error",
        text: error instanceof Error ? error.message : "删除知识库失败。",
      });
    } finally {
      setDeletingKnowledgeBaseId("");
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedKnowledgeBase) {
      setUploadNotice({ type: "error", text: "请先选择知识库。" });
      return;
    }
    if (!selectedFile) {
      setUploadNotice({
        type: "error",
        text: "请先选择一个 .txt、.md、.pdf 或 .docx 文件。",
      });
      return;
    }

    setUploadLoading(true);
    setUploadNotice(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("knowledge_base_id", selectedKnowledgeBase.id);

      const response = await authFetch(`${apiBaseUrl}/ingest/upload`, {
        method: "POST",
        body: formData,
      });

      const payload = (await response.json()) as
        | IngestResponse
        | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "文件上传入库失败。",
        );
      }

      const successPayload = payload as IngestResponse;
      setUploadNotice({
        type: "success",
        text: `${successPayload.knowledge_base_name} 已入库文档 ${successPayload.filename}（${successPayload.file_type}），解析 ${successPayload.character_count} 个字符，新增 ${successPayload.chunks} 个 chunk，跳过 ${successPayload.skipped} 个重复 chunk。`,
      });
      setSelectedFile(null);
      await loadDocuments(selectedKnowledgeBase.id);
      await loadDocumentCounts(knowledgeBases);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "文件上传入库失败。");
        return;
      }
      setUploadNotice({
        type: "error",
        text: error instanceof Error ? error.message : "文件上传入库失败。",
      });
    } finally {
      setUploadLoading(false);
    }
  }

  async function handleDeleteDocument(source: string) {
    if (!selectedKnowledgeBase) {
      return;
    }

    setDeletingSource(source);
    setDeleteNotice(null);

    try {
      const response = await authFetch(`${apiBaseUrl}/documents`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source,
          knowledge_base_id: selectedKnowledgeBase.id,
        }),
      });

      const payload = (await response.json()) as
        | DeleteDocumentResponse
        | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "删除文档失败。",
        );
      }

      const successPayload = payload as DeleteDocumentResponse;
      setDeleteNotice({
        type: "success",
        text: `${successPayload.knowledge_base_name} 中的文档已删除：${successPayload.source}`,
      });
      await loadDocuments(selectedKnowledgeBase.id);
      await loadDocumentCounts(knowledgeBases);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "删除文档失败。");
        return;
      }
      setDeleteNotice({
        type: "error",
        text: error instanceof Error ? error.message : "删除文档失败。",
      });
    } finally {
      setDeletingSource("");
    }
  }

  async function handleDeleteSession(sessionId: string) {
    setDeletingSessionId(sessionId);
    setSessionNotice(null);

    try {
      const response = await authFetch(`${apiBaseUrl}/sessions/${sessionId}`, {
        method: "DELETE",
      });
      const payload = (await response.json()) as
        | DeleteSessionResponse
        | { detail?: string };

      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "删除会话失败。",
        );
      }

      setSessionNotice({
        type: "success",
        text: (payload as DeleteSessionResponse).message,
      });
      await reloadSessions();
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "删除会话失败。");
        return;
      }
      setSessionNotice({
        type: "error",
        text: error instanceof Error ? error.message : "删除会话失败。",
      });
    } finally {
      setDeletingSessionId("");
    }
  }

  async function fetchUsers(page = 1, pageSize = USER_PAGE_SIZE) {
    const response = await authFetch(
      `${apiBaseUrl}/admin/users?page=${page}&page_size=${pageSize}`,
    );
    const payload = (await response.json()) as { users: UserListItem[]; total: number } | { detail?: string };
    if (!response.ok) {
      throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "获取用户列表失败。");
    }
    const data = payload as { users: UserListItem[]; total: number };
    setUsers(data.users);
    setUserTotal(data.total);
  }

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = newUsername.trim();
    if (!trimmedName || !newPassword) {
      setUserNotice({ type: "error", text: "请填写用户名和密码。" });
      return;
    }
    setCreatingUser(true);
    setUserNotice(null);
    try {
      const response = await authFetch(`${apiBaseUrl}/admin/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: trimmedName, password: newPassword, role: newRole }),
      });
      const payload = (await response.json()) as UserListItem | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : "创建用户失败。");
      }
      const created = payload as UserListItem;
      setUserNotice({ type: "success", text: `用户 ${created.username} 已创建。` });
      setNewUsername("");
      setNewPassword("");
      setNewRole("user");
      await fetchUsers(userPage, USER_PAGE_SIZE);
    } catch (error) {
      if (error instanceof AuthError) { handleAuthAwareError(error, "创建用户失败。"); return; }
      setUserNotice({ type: "error", text: error instanceof Error ? error.message : "创建用户失败。" });
    } finally {
      setCreatingUser(false);
    }
  }

  async function handleDeleteUser(userId: string, username: string) {
    if (!window.confirm(`确定要删除用户 ${username} 吗？`)) return;
    setDeletingUserId(userId);
    setUserNotice(null);
    try {
      const response = await authFetch(`${apiBaseUrl}/admin/users/${userId}`, { method: "DELETE" });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail || "删除用户失败。");
      }
      setUserNotice({ type: "success", text: `用户 ${username} 已删除。` });
      await fetchUsers(userPage, USER_PAGE_SIZE);
    } catch (error) {
      if (error instanceof AuthError) { handleAuthAwareError(error, "删除用户失败。"); return; }
      setUserNotice({ type: "error", text: error instanceof Error ? error.message : "删除用户失败。" });
    } finally {
      setDeletingUserId("");
    }
  }

  function handleLogout() {
    clearStoredAuth();
    router.replace("/login");
  }

  if (!authReady) {
    return (
      <main className={styles.page}>
        <section className={styles.card}>
          <p className={styles.emptyState}>正在验证管理员身份...</p>
        </section>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div
          className={styles.headerSearch}
          onFocus={() => setSearchOpen(true)}
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
              setSearchOpen(false);
            }
          }}
        >
          <span className={styles.searchIcon} aria-hidden="true" />
          <input
            className={styles.headerSearchInput}
            value={knowledgeBaseQuery}
            onChange={(event) => {
              setKnowledgeBaseQuery(event.target.value);
              setSearchOpen(true);
            }}
            placeholder="筛选知识库..."
            aria-label="筛选知识库"
          />
          {searchOpen && knowledgeBaseQuery.trim() ? (
            <div className={styles.searchMenu}>
              <div className={styles.searchGroup}>
                <p className={styles.searchGroupLabel}>知识库</p>
                {matchingKnowledgeBases.map((item) => (
                  <button
                    key={item.id}
                    className={styles.searchResult}
                    onClick={() => {
                      setActiveView("knowledge-bases");
                      setKnowledgeBaseDetailOpen(false);
                      setFocusedKnowledgeBaseId(item.id);
                      setFocusedDocumentSource("");
                      setKnowledgeBasePage(1);
                      setSelectedKnowledgeBaseId(item.id);
                      setKnowledgeBaseQuery("");
                      setSearchOpen(false);
                    }}
                    type="button"
                  >
                    <strong>{item.name}</strong>
                    <span>{item.slug} · {item.collection_name}</span>
                  </button>
                ))}
                {!matchingKnowledgeBases.length ? (
                  <p className={styles.searchEmpty}>没有匹配的知识库</p>
                ) : null}
              </div>

              <div className={styles.searchGroup}>
                <p className={styles.searchGroupLabel}>文档</p>
                {searchDocuments.map(({ document, knowledgeBase }) => (
                  <button
                    key={`${knowledgeBase.id}:${document.source}`}
                    className={styles.searchResult}
                    onClick={() => {
                      setActiveView("knowledge-bases");
                      setSelectedKnowledgeBaseId(knowledgeBase.id);
                      setKnowledgeBaseDetailOpen(true);
                      setFocusedKnowledgeBaseId("");
                      setFocusedDocumentSource(document.source);
                      setKnowledgeBaseQuery("");
                      setSearchOpen(false);
                    }}
                    type="button"
                  >
                    <strong>{document.filename}</strong>
                    <span>{knowledgeBase.name}</span>
                  </button>
                ))}
                {searchLoading ? (
                  <p className={styles.searchEmpty}>正在搜索文档...</p>
                ) : null}
                {!searchLoading && !searchDocuments.length ? (
                  <p className={styles.searchEmpty}>没有匹配的文档</p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
        <div className={styles.headerActions}>
          <Link className={styles.secondaryLink} href="/">
            返回聊天
          </Link>
          <div className={styles.adminIdentity}>
            <span className={styles.adminAvatar}>
              {(currentUser?.username || "A").slice(0, 1).toUpperCase()}
            </span>
            <span>
              <span className={styles.adminUserName}>{currentUser?.username}</span>
              <span className={styles.adminUserRole}>管理员</span>
            </span>
          </div>
        </div>
      </header>

      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>M</span>
          <span>
            <strong>myAgent 管理后台</strong>
            <small>Knowledge Console</small>
          </span>
        </div>

        <p className={styles.navLabel}>导航</p>
        <nav className={styles.menuList}>
            {adminMenus.map((menu) => (
              <button
                key={menu.key}
                className={
                  activeView === menu.key ? styles.menuItemActive : styles.menuItem
                }
                onClick={() => {
                  setActiveView(menu.key);
                  setKnowledgeBaseDetailOpen(false);
                  setFocusedKnowledgeBaseId("");
                  setFocusedDocumentSource("");
                  setKnowledgeBasePage(1);
                }}
                type="button"
              >
                <span className={styles.menuIcon}>{menu.icon}</span>
                <span className={styles.menuContent}>
                  <span className={styles.menuLabel}>{menu.label}</span>
                </span>
              </button>
            ))}
        </nav>

        <div className={styles.sidebarFooter}>
          <div>
            <strong>{currentUser?.username}</strong>
            <span>管理员账户</span>
          </div>
          <button className={styles.sidebarLogout} onClick={handleLogout} type="button">
            退出
          </button>
        </div>
      </aside>

      <section className={styles.workspace}>
        <section className={styles.content}>
          <div className={styles.contentHeader}>
            <div>
              <p className={styles.contentEyebrow}>
                首页 / {activeMenu.label}
                {knowledgeBaseDetailOpen ? " / 文档管理" : ""}
              </p>
              <h2 className={styles.contentTitle}>
                {knowledgeBaseDetailOpen ? "文档管理" : activeMenu.label}
              </h2>
              <p className={styles.contentDescription}>
                {knowledgeBaseDetailOpen
                  ? `${selectedKnowledgeBase?.name || "-"} · ${collection || "-"}`
                  : activeMenu.description}
              </p>
            </div>
            <div className={styles.contentHeaderActions}>
              {activeView === "knowledge-bases" && !knowledgeBaseDetailOpen ? (
                <button
                  className={styles.primaryButton}
                  onClick={() => {
                    setKnowledgeBaseNotice(null);
                    setNewKnowledgeBaseName("");
                    setCreateKnowledgeBaseOpen(true);
                  }}
                  type="button"
                >
                  + 新建知识库
                </button>
              ) : null}
              {focusedKnowledgeBaseId && !knowledgeBaseDetailOpen ? (
                <button
                  className={styles.backButton}
                  onClick={() => {
                    setFocusedKnowledgeBaseId("");
                    setKnowledgeBasePage(1);
                  }}
                  type="button"
                >
                  查看全部知识库
                </button>
              ) : null}
              {focusedDocumentSource && knowledgeBaseDetailOpen ? (
                <button
                  className={styles.backButton}
                  onClick={() => setFocusedDocumentSource("")}
                  type="button"
                >
                  查看全部文档
                </button>
              ) : null}
              {knowledgeBaseDetailOpen ? (
                <button
                  className={styles.backButton}
                  onClick={() => {
                    setKnowledgeBaseDetailOpen(false);
                    setFocusedDocumentSource("");
                  }}
                  type="button"
                >
                  返回知识库
                </button>
              ) : null}
            </div>
          </div>

          {activeView === "overview" ? (
            <>
              <section className={styles.summaryGrid}>
                <OverviewMetric
                  icon="layers"
                  label="知识库"
                  value={String(knowledgeBases.length)}
                />
                <OverviewMetric
                  icon="doc"
                  label="文档总数"
                  value={String(totalDocumentCount)}
                />
                <OverviewMetric
                  icon="chat"
                  label="聊天会话"
                  value={String(sessions.length)}
                />
                <OverviewMetric
                  icon="grid"
                  label="服务状态"
                  value={health === "ok" ? "正常" : health}
                />
              </section>
              <div className={styles.overviewActions}>
              <button
                className={styles.refreshButton}
                onClick={() => {
                  void loadHealth();
                  void loadDocumentCounts(knowledgeBases);
                  void reloadSessions();
                }}
                type="button"
              >
                刷新统计
              </button>
              </div>
              {docError ? <NoticeBox notice={{ type: "error", text: docError }} /> : null}
            </>
          ) : null}

          {activeView === "knowledge-bases" ? (
            knowledgeBaseDetailOpen ? (
              <section className={styles.card}>
                <div className={styles.cardHeader}>
                  <div>
                    <h3 className={styles.cardTitle}>文档列表</h3>
                    <p className={styles.cardSubtitle}>上传文件并管理当前知识库中的文档</p>
                  </div>
                  {docLoading ? <span className={styles.helper}>加载中...</span> : null}
                </div>

                <form className={styles.uploadToolbar} onSubmit={handleUpload}>
                  <input
                    id="upload-file"
                    className={styles.fileInput}
                    type="file"
                    accept=".txt,.md,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    onChange={(event) =>
                      setSelectedFile(
                        event.target.files && event.target.files[0]
                          ? event.target.files[0]
                          : null,
                      )
                    }
                  />
                  <button
                    className={styles.primaryButton}
                    disabled={uploadLoading}
                    type="submit"
                  >
                    {uploadLoading ? "上传中..." : "上传文档"}
                  </button>
                </form>

                {selectedFile ? (
                  <p className={styles.selectedFile}>已选择：{selectedFile.name}</p>
                ) : null}
                {uploadNotice ? <NoticeBox notice={uploadNotice} /> : null}

                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>文档</th>
                        <th>类型</th>
                        <th>状态</th>
                        <th>存储</th>
                        <th>大小</th>
                        <th>Chunks</th>
                        <th>更新时间</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleDocuments.map((document) => (
                        <tr key={document.source}>
                          <td className={styles.documentName}>{document.filename}</td>
                          <td>{document.file_type}</td>
                          <td>
                            <span className={styles.statusBadge}>
                              {document.status === "indexed" ? "已入库" : document.status}
                            </span>
                          </td>
                          <td>{document.storage_provider}</td>
                          <td>
                            {document.file_size
                              ? `${(document.file_size / 1024).toFixed(1)} KB`
                              : "-"}
                          </td>
                          <td>{document.chunks}</td>
                          <td>
                            {document.uploaded_at
                              ? new Date(document.uploaded_at).toLocaleString("zh-CN")
                              : "-"}
                          </td>
                          <td>
                            <button
                              className={styles.deleteButton}
                              disabled={deletingSource === document.source}
                              onClick={() => void handleDeleteDocument(document.source)}
                              type="button"
                            >
                              {deletingSource === document.source ? "删除中..." : "删除"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {!visibleDocuments.length ? (
                  <p className={styles.emptyState}>当前知识库下还没有文档，可以先上传一个文件。</p>
                ) : null}
                <Pagination
                  currentPage={docPage}
                  pageSize={DOC_PAGE_SIZE}
                  totalItems={docTotal}
                  itemLabel="个文档"
                  onPageChange={setDocPage}
                />
                {deleteNotice ? <NoticeBox notice={deleteNotice} /> : null}
              </section>
            ) : (
            <>
              <section className={styles.summaryGrid}>
                <OverviewMetric
                  icon="layers"
                  label="知识库"
                  value={String(knowledgeBases.length)}
                />
                <OverviewMetric
                  icon="doc"
                  label="文档总数"
                  value={String(totalDocumentCount)}
                />
                <OverviewMetric
                  icon="upload"
                  label="含文档知识库"
                  value={String(knowledgeBasesWithDocuments)}
                />
                <OverviewMetric
                  icon="chat"
                  label="会话用户"
                  value={String(conversationUserCount)}
                />
              </section>

            <section className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <h3 className={styles.cardTitle}>知识库管理</h3>
                  <p className={styles.cardSubtitle}>
                    点击知识库名称进入文档上传与文档管理页面。
                  </p>
                </div>
              </div>

              <p className={styles.helperText}>
                删除规则：只要该知识库下还有文档或会话，就暂时不能删除。
              </p>

              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>名称</th>
                      <th>Collection</th>
                      <th>Embedding 模型</th>
                      <th>文档数</th>
                      <th>创建时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedKnowledgeBases.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <button
                            className={styles.knowledgeBaseLink}
                            onClick={() => {
                              setSelectedKnowledgeBaseId(item.id);
                              setKnowledgeBaseDetailOpen(true);
                              setFocusedKnowledgeBaseId("");
                              setFocusedDocumentSource("");
                            }}
                            type="button"
                          >
                            {item.name}
                          </button>
                        </td>
                        <td>{item.collection_name}</td>
                        <td>{item.embedding_model || "-"}</td>
                        <td>{item.document_count}</td>
                        <td>{new Date(item.created_at).toLocaleString("zh-CN")}</td>
                        <td>
                          <button
                            className={styles.deleteButton}
                            disabled={deletingKnowledgeBaseId === item.id}
                            onClick={() => void handleDeleteKnowledgeBase(item)}
                            type="button"
                          >
                            {deletingKnowledgeBaseId === item.id ? "删除中..." : "删除"}
                          </button>
                        </td>
                      </tr>
                    ))}
                    {!visibleKnowledgeBases.length ? (
                      <tr>
                        <td colSpan={6} className={styles.emptyTableCell}>
                          没有找到匹配的知识库
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>

              <Pagination
                currentPage={safeKnowledgeBasePage}
                pageSize={KNOWLEDGE_BASE_PAGE_SIZE}
                totalItems={visibleKnowledgeBases.length}
                itemLabel="个知识库"
                onPageChange={setKnowledgeBasePage}
              />

              {!createKnowledgeBaseOpen && knowledgeBaseNotice ? (
                <NoticeBox notice={knowledgeBaseNotice} />
              ) : null}
            </section>
            </>
            )
          ) : null}

          {activeView === "users" ? (
            <section className={styles.card}>
              <div className={styles.cardHeader}>
                <h3 className={styles.cardTitle}>用户管理</h3>
                <p className={styles.cardSubtitle}>管理可登录后台的用户，包括管理员和普通用户</p>
              </div>

              <form className={styles.createToolbar} onSubmit={handleCreateUser}>
                <label className={styles.label} htmlFor="new-username">用户名</label>
                <input id="new-username" className={styles.input} value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="2-100 个字符" />
                <label className={styles.label} htmlFor="new-password">密码</label>
                <input id="new-password" className={styles.input} type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="至少 6 个字符" />
                <label className={styles.label} htmlFor="new-role">角色</label>
                <select id="new-role" className={styles.select} value={newRole} onChange={(e) => setNewRole(e.target.value as "user" | "admin")}>
                  <option value="user">普通用户 (user)</option>
                  <option value="admin">管理员 (admin)</option>
                </select>
                <button className={styles.primaryButton} disabled={creatingUser} type="submit">
                  {creatingUser ? "创建中..." : "创建用户"}
                </button>
              </form>

              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>用户名</th>
                      <th>角色</th>
                      <th>创建时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id}>
                        <td>{user.username}</td>
                        <td>
                          <span className={styles.statusBadge}>
                            {user.role === "admin" ? "管理员" : "普通用户"}
                          </span>
                        </td>
                        <td>{new Date(user.created_at).toLocaleString("zh-CN")}</td>
                        <td>
                          <button
                            className={styles.deleteButton}
                            disabled={deletingUserId === user.id}
                            onClick={() => void handleDeleteUser(user.id, user.username)}
                            type="button"
                          >
                            {deletingUserId === user.id ? "删除中..." : "删除"}
                          </button>
                        </td>
                      </tr>
                    ))}
                    {!users.length ? (
                      <tr>
                        <td colSpan={4} className={styles.emptyTableCell}>暂无用户数据</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <p className={styles.helperText}>共 {userTotal} 个用户</p>
              <Pagination
                currentPage={userPage}
                pageSize={USER_PAGE_SIZE}
                totalItems={userTotal}
                itemLabel="个用户"
                onPageChange={setUserPage}
              />
              {userNotice ? <NoticeBox notice={userNotice} /> : null}
            </section>
          ) : null}

          {activeView === "sessions" ? (
            <section className={styles.card}>
              <div className={styles.cardHeader}>
                <h3 className={styles.cardTitle}>聊天会话</h3>
                {sessionLoading ? <span className={styles.helper}>加载中...</span> : null}
              </div>

              <div className={styles.sessionLayout}>
                <div className={styles.sessionTableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>标题</th>
                        <th>用户</th>
                        <th>知识库</th>
                        <th>消息数</th>
                        <th>更新时间</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((session) => (
                        <tr
                          key={session.id}
                          className={
                            session.id === selectedSessionId ? styles.activeRow : ""
                          }
                        >
                          <td>
                            <button
                              className={styles.sessionSelectButton}
                              onClick={() => void loadSessionMessages(session.id)}
                              type="button"
                            >
                              {session.title}
                            </button>
                          </td>
                          <td>{session.owner_username || "-"}</td>
                          <td>{session.knowledge_base_name || "-"}</td>
                          <td>{session.message_count}</td>
                          <td>{new Date(session.updated_at).toLocaleString("zh-CN")}</td>
                          <td>
                            <button
                              className={styles.deleteButton}
                              disabled={deletingSessionId === session.id}
                              onClick={() => void handleDeleteSession(session.id)}
                              type="button"
                            >
                              {deletingSessionId === session.id ? "删除中..." : "删除"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className={styles.messageViewer}>
                  <h3 className={styles.viewerTitle}>
                    {selectedSession ? `${selectedSession.title} 的消息详情` : "会话消息详情"}
                  </h3>
                  {sessionMessages.length ? (
                    <div className={styles.messageList}>
                      {sessionMessages.map((message) => (
                        <article key={message.id} className={styles.messageCard}>
                          <div className={styles.messageCardHeader}>
                            <strong>{message.role === "user" ? "用户" : "Agent"}</strong>
                            <span>
                              {new Date(message.created_at).toLocaleString("zh-CN")}
                            </span>
                          </div>
                          <p className={styles.messageContent}>{message.content}</p>
                          {message.role === "assistant" ? (
                            <div className={styles.messageMeta}>
                              <span>route: {message.route || "-"}</span>
                              <span>retrieval: {message.retrieval_quality || "-"}</span>
                              <span>sources: {message.source_count}</span>
                            </div>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className={styles.emptyState}>选择一个会话后，这里会显示完整聊天记录。</p>
                  )}
                </div>
              </div>

              <Pagination
                currentPage={sessionPage}
                pageSize={SESSION_PAGE_SIZE}
                totalItems={sessionTotal}
                itemLabel="个会话"
                onPageChange={setSessionPage}
              />
              {sessionNotice ? <NoticeBox notice={sessionNotice} /> : null}
            </section>
          ) : null}
        </section>
      </section>
      {createKnowledgeBaseOpen ? (
        <div className={styles.modalOverlay} role="presentation">
          <div
            aria-labelledby="create-knowledge-base-title"
            aria-modal="true"
            className={styles.modal}
            role="dialog"
          >
            <div className={styles.modalHeader}>
              <div>
                <h3 className={styles.modalTitle} id="create-knowledge-base-title">
                  创建知识库
                </h3>
                <p className={styles.modalSubtitle}>
                  创建一个新的知识库，用于存储、向量化和检索文档。
                </p>
              </div>
              <button
                aria-label="关闭创建知识库弹窗"
                className={styles.modalCloseButton}
                onClick={() => {
                  setCreateKnowledgeBaseOpen(false);
                  setKnowledgeBaseNotice(null);
                }}
                type="button"
              >
                ×
              </button>
            </div>

            <form className={styles.modalForm} onSubmit={handleCreateKnowledgeBase}>
              <label className={styles.label} htmlFor="knowledge-base-name">
                知识库名称 <span style={{ color: "var(--danger)" }}>*</span>
              </label>
              <input
                required
                autoFocus
                id="knowledge-base-name"
                className={styles.input}
                value={newKnowledgeBaseName}
                onChange={(event) => setNewKnowledgeBaseName(event.target.value)}
                placeholder="例如：产品文档库"
              />

              <label className={styles.label} htmlFor="kb-collection-name">
                Collection 名称 <span style={{ color: "var(--danger)" }}>*</span>
              </label>
              <input
                required
                id="kb-collection-name"
                className={styles.input}
                value={newCollectionName}
                onChange={(event) => setNewCollectionName(event.target.value.replace(/[^a-z0-9_]/g, ""))}
                placeholder="小写字母、数字、下划线"
                pattern="^[a-z0-9][a-z0-9_]*$"
                title="只能包含小写字母、数字和下划线"
              />

              <label className={styles.label} htmlFor="kb-embedding-model">
                Embedding 模型 <span style={{ color: "var(--danger)" }}>*</span>
              </label>
              <select
                required
                id="kb-embedding-model"
                className={styles.select}
                value={newEmbeddingModel}
                onChange={(event) => setNewEmbeddingModel(event.target.value)}
              >
                <option value="">请选择...</option>
                <option value="text-embedding-v4">text-embedding-v4 (通义千问)</option>
                <option value="text-embedding-v3">text-embedding-v3 (通义千问)</option>
              </select>

              {knowledgeBaseNotice ? <NoticeBox notice={knowledgeBaseNotice} /> : null}
              <div className={styles.modalActions}>
                <button
                  className={styles.backButton}
                  onClick={() => {
                    setCreateKnowledgeBaseOpen(false);
                    setKnowledgeBaseNotice(null);
                  }}
                  type="button"
                >
                  取消
                </button>
                <button
                  className={styles.primaryButton}
                  disabled={creatingKnowledgeBase}
                  type="submit"
                >
                  {creatingKnowledgeBase ? "创建中..." : "创建"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </main>
  );
}

function SidebarStat({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.sidebarStat}>
      <span className={styles.sidebarStatLabel}>{label}</span>
      <span className={styles.sidebarStatValue}>{value}</span>
    </div>
  );
}

function OverviewMetric({
  icon,
  label,
  value,
}: {
  icon: MenuIconVariant;
  label: string;
  value: string;
}) {
  return (
    <div className={styles.overviewMetric}>
      <span className={styles.metricIcon}>
        <MenuIcon variant={icon} />
      </span>
      <span className={styles.metricContent}>
        <span className={styles.overviewMetricLabel}>{label}</span>
        <span className={styles.overviewMetricValue}>{value}</span>
      </span>
    </div>
  );
}

function NoticeBox({ notice }: { notice: Notice }) {
  return (
    <div
      className={notice.type === "success" ? styles.noticeSuccess : styles.noticeError}
    >
      {notice.text}
    </div>
  );
}
