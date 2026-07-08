"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { MenuIcon, type MenuIconVariant } from "../../components/MenuIcon";
import { Modal } from "../../components/Modal";
import { Pagination } from "../../components/Pagination/Pagination";
import { Select } from "../../components/Select";
import { admin, common } from "../messages";
import styles from "./page.module.css";
import {
  apiBaseUrl,
  DeleteDocumentResponse,
  DeleteKnowledgeBaseResponse,
  DeleteSessionResponse,
  DocumentInfo,
  DocumentsResponse,
  IngestResponse,
  IngestionTaskListResponse,
  IngestionTaskResponse,
  KnowledgeBaseResponse,
  MessageResponse,
  RetrievalTestResponse,
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
import { admin as adminMessages } from "../messages";

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

const LIVE_INGESTION_STATUSES = new Set(["pending", "queued", "running", "retrying"]);
const KNOWLEDGE_BASE_PAGE_SIZE = 6;
const INGESTION_POLL_INTERVAL_MS = 3000;

type AdminView =
  | "overview"
  | "knowledge-bases"
  | "retrieval-test"
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
    key: "retrieval-test",
    label: "检索测试",
    description: "调试问题召回片段和分数",
    icon: <MenuIcon variant="path" />,
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
  const [ingestionTasks, setIngestionTasks] = useState<IngestionTaskResponse[]>([]);
  const [taskLoading, setTaskLoading] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [retryingTaskId, setRetryingTaskId] = useState("");
  const [cancellingTaskId, setCancellingTaskId] = useState("");
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
  const [chunkingSource, setChunkingSource] = useState("");
  const [retrievalKbId, setRetrievalKbId] = useState("");
  const [retrievalQuestion, setRetrievalQuestion] = useState("");
  const [retrievalTopK, setRetrievalTopK] = useState(6);
  const [retrievalUseRerank, setRetrievalUseRerank] = useState(false);
  const [retrievalLoading, setRetrievalLoading] = useState(false);
  const [retrievalNotice, setRetrievalNotice] = useState<Notice | null>(null);
  const [retrievalResult, setRetrievalResult] = useState<RetrievalTestResponse | null>(null);
  const [chunkDetailOpen, setChunkDetailOpen] = useState(false);
  const [chunkDetailSource, setChunkDetailSource] = useState("");
  const [chunkDetailDoc, setChunkDetailDoc] = useState("");
  type ChunkItem = { id: number; text: string };
  const [chunkItems, setChunkItems] = useState<ChunkItem[]>([]);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [newKnowledgeBaseName, setNewKnowledgeBaseName] = useState("");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [newEmbeddingModel, setNewEmbeddingModel] = useState("");
  const [createKnowledgeBaseOpen, setCreateKnowledgeBaseOpen] = useState(false);
  const [knowledgeBaseNotice, setKnowledgeBaseNotice] = useState<Notice | null>(null);
  const [creatingKnowledgeBase, setCreatingKnowledgeBase] = useState(false);
  const [deletingKnowledgeBaseId, setDeletingKnowledgeBaseId] = useState("");
  const [editingKbId, setEditingKbId] = useState("");
  const [editKbName, setEditKbName] = useState("");
  const [renamingKb, setRenamingKb] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

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

  type AdminStats = {
    knowledge_bases: number; users: number;
    documents: { total: number; chunks: number; size: number; indexed: number; pending: number; failed: number };
    milvus: { collections: number; vectors: number };
    kb_breakdown: { name: string; documents: number; chunks: number; size: number; collection: string }[];
  };
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [statsRefreshing, setStatsRefreshing] = useState(false);

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

  const selectedTask = useMemo(
    () => ingestionTasks.find((item) => item.id === selectedTaskId) ?? ingestionTasks[0] ?? null,
    [ingestionTasks, selectedTaskId],
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

  const hasLiveIngestionWork = useMemo(
    () =>
      documents.some((document) => isLiveIngestionStatus(document.status)) ||
      ingestionTasks.some((task) => isLiveIngestionStatus(task.status)),
    [documents, ingestionTasks],
  );

  useEffect(() => {
    void bootstrapAdmin();
  }, []);

  useEffect(() => {
    if (authReady && selectedKnowledgeBaseId) {
      void loadDocuments(selectedKnowledgeBaseId);
      void loadIngestionTasks(selectedKnowledgeBaseId);
    }
  }, [authReady, selectedKnowledgeBaseId, docPage]);

  useEffect(() => {
    if (!retrievalKbId && selectedKnowledgeBaseId) {
      setRetrievalKbId(selectedKnowledgeBaseId);
    }
  }, [retrievalKbId, selectedKnowledgeBaseId]);

  useEffect(() => {
    if (!authReady || !selectedKnowledgeBaseId || !hasLiveIngestionWork) {
      return;
    }

    let cancelled = false;
    const refreshIngestionState = async () => {
      if (cancelled) {
        return;
      }
      await Promise.all([
        loadDocuments(selectedKnowledgeBaseId),
        loadIngestionTasks(selectedKnowledgeBaseId),
        loadDocumentCounts(knowledgeBases),
      ]);
    };

    const timer = window.setInterval(() => {
      void refreshIngestionState();
    }, INGESTION_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [authReady, selectedKnowledgeBaseId, hasLiveIngestionWork, docPage, knowledgeBases]);

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
      try { await fetchStats(); } catch { /* stats fail silently */ }
      setAuthReady(true);
    } catch (error) {
      handleAuthAwareError(error, adminMessages.bootstrap);
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
          : adminMessages.knowledgeBases.fetchListFailed,
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
          : adminMessages.sessions.fetchSessionsFailed,
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
            : adminMessages.documents.fetchFailed,
        );
      }

      const successPayload = payload as DocumentsResponse;
      setCollection(successPayload.collection);
      setDocuments(successPayload.documents);
      setDocTotal(successPayload.total || 0);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, adminMessages.documents.fetchFailed);
        return;
      }
      setDocError(error instanceof Error ? error.message : adminMessages.documents.fetchFailed);
    } finally {
      setDocLoading(false);
    }
  }

  async function loadIngestionTasks(knowledgeBaseId: string) {
    setTaskLoading(true);
    try {
      const response = await authFetch(
        `${apiBaseUrl}/ingestion/tasks?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}&limit=20`,
      );
      const payload = (await response.json()) as
        | IngestionTaskListResponse
        | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : adminMessages.tasks.fetchFailed,
        );
      }
      const tasks = (payload as IngestionTaskListResponse).tasks;
      setIngestionTasks(tasks);
      setSelectedTaskId((current) => {
        const currentTask = tasks.find((item) => item.id === current);
        if (currentTask && isLiveIngestionStatus(currentTask.status)) {
          return current;
        }
        const liveTask = tasks.find((item) => isLiveIngestionStatus(item.status));
        if (liveTask) {
          return liveTask.id;
        }
        if (currentTask) {
          return current;
        }
        return tasks[0]?.id || "";
      });
    } catch {
      setIngestionTasks([]);
      setSelectedTaskId("");
    } finally {
      setTaskLoading(false);
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
          : adminMessages.sessions.fetchMessagesFailed,
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
        handleAuthAwareError(error, adminMessages.sessions.fetchSessionsFailed);
        return;
      }
      setSessionNotice({
        type: "error",
        text: error instanceof Error ? error.message : adminMessages.sessions.fetchSessionsFailed,
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
      setKnowledgeBaseNotice({ type: "error", text: adminMessages.forms.requiredFields });
      return;
    }
    if (!/^[a-z0-9][a-z0-9_]*$/.test(trimmedCollection)) {
      setKnowledgeBaseNotice({ type: "error", text: adminMessages.forms.collectionFormatError });
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
            : adminMessages.knowledgeBases.createFailed,
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
        handleAuthAwareError(error, adminMessages.knowledgeBases.createFailed);
        return;
      }
      setKnowledgeBaseNotice({
        type: "error",
        text: error instanceof Error ? error.message : adminMessages.knowledgeBases.createFailed,
      });
    } finally {
      setCreatingKnowledgeBase(false);
    }
  }

  async function handleRenameKnowledgeBase(knowledgeBaseId: string) {
    const trimmedName = editKbName.trim();
    if (!trimmedName) {
      setKnowledgeBaseNotice({ type: "error", text: adminMessages.knowledgeBases.nameRequired });
      return;
    }
    setRenamingKb(true);
    try {
      const response = await authFetch(`${apiBaseUrl}/knowledge-bases/${knowledgeBaseId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmedName }),
      });
      const payload = (await response.json()) as KnowledgeBaseResponse | { detail?: string };
      if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : adminMessages.knowledgeBases.renameGenericFailed);
      setKnowledgeBases((prev) => prev.map((kb) => (kb.id === knowledgeBaseId ? (payload as KnowledgeBaseResponse) : kb)));
      setEditingKbId("");
      setEditKbName("");
      setKnowledgeBaseNotice({ type: "success", text: adminMessages.knowledgeBases.renameSuccess });
    } catch (error) {
      if (error instanceof AuthError) { handleAuthAwareError(error, adminMessages.knowledgeBases.renameGenericFailed); return; }
      setKnowledgeBaseNotice({ type: "error", text: error instanceof Error ? error.message : adminMessages.knowledgeBases.renameGenericFailed });
    } finally {
      setRenamingKb(false);
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
            : adminMessages.knowledgeBases.deleteFailed,
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
        handleAuthAwareError(error, adminMessages.knowledgeBases.deleteFailed);
        return;
      }
      setKnowledgeBaseNotice({
        type: "error",
        text: error instanceof Error ? error.message : adminMessages.knowledgeBases.deleteFailed,
      });
    } finally {
      setDeletingKnowledgeBaseId("");
    }
  }

  async function handleUpload() {
    if (!selectedKnowledgeBase) {
      setUploadNotice({ type: "error", text: adminMessages.upload.selectKbFirst });
      return;
    }
    if (!selectedFile) {
      setUploadNotice({
        type: "error",
        text: adminMessages.upload.fileTypeError,
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
            : adminMessages.upload.uploadFailed,
        );
      }

      const successPayload = payload as IngestResponse;
      setUploadNotice({
        type: "success",
        text: adminMessages.upload.successTemplate
          .replace("{kb_name}", successPayload.knowledge_base_name)
          .replace("{filename}", successPayload.filename)
          .replace("{file_type}", successPayload.file_type),
      });
      setSelectedFile(null);
      setUploadModalOpen(false);
      void Promise.all([
        loadDocuments(selectedKnowledgeBase.id),
        loadIngestionTasks(selectedKnowledgeBase.id),
        loadDocumentCounts(knowledgeBases),
      ]);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, adminMessages.upload.uploadFailed);
        return;
      }
      setUploadNotice({
        type: "error",
        text: error instanceof Error ? error.message : adminMessages.upload.uploadFailed,
      });
    } finally {
      setUploadLoading(false);
    }
  }

  async function handleRetrievalTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = retrievalQuestion.trim();
    if (!retrievalKbId) {
      setRetrievalNotice({ type: "error", text: "请先选择知识库。" });
      return;
    }
    if (!question) {
      setRetrievalNotice({ type: "error", text: "请输入测试问题。" });
      return;
    }

    setRetrievalLoading(true);
    setRetrievalNotice(null);
    setRetrievalResult(null);
    try {
      const response = await authFetch(`${apiBaseUrl}/retrieval/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          knowledge_base_ids: [retrievalKbId],
          top_k: retrievalTopK,
          use_rerank: retrievalUseRerank,
        }),
      });
      const payload = (await response.json()) as RetrievalTestResponse | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "检索测试失败。",
        );
      }
      setRetrievalResult(payload as RetrievalTestResponse);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "检索测试失败。");
        return;
      }
      setRetrievalNotice({
        type: "error",
        text: error instanceof Error ? error.message : "检索测试失败。",
      });
    } finally {
      setRetrievalLoading(false);
    }
  }

  async function viewChunks(source: string, filename: string) {
    if (!selectedKnowledgeBase) return;
    setChunkDetailSource(source);
    setChunkDetailDoc(filename);
    setChunkDetailOpen(true);
    setChunkLoading(true);
    try {
      const response = await authFetch(
        `${apiBaseUrl}/documents/chunks?knowledge_base_id=${encodeURIComponent(selectedKnowledgeBase.id)}&source=${encodeURIComponent(source)}`,
      );
      const payload = (await response.json()) as { chunks: ChunkItem[]; total: number } | { detail?: string };
      if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : adminMessages.chunks.fetchFailed);
      setChunkItems((payload as { chunks: ChunkItem[] }).chunks);
    } catch {
      setChunkItems([]);
    } finally {
      setChunkLoading(false);
    }
  }

  async function handleChunkDocument(source: string) {
    if (!selectedKnowledgeBase) return;
    setChunkingSource(source);
    setDeleteNotice(null);
    try {
      const response = await authFetch(`${apiBaseUrl}/documents/chunk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, knowledge_base_id: selectedKnowledgeBase.id }),
      });
      const payload = (await response.json()) as IngestResponse | { detail?: string };
      if (!response.ok) throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : adminMessages.knowledgeBases.chunkFailed);
      const successPayload = payload as IngestResponse;
      setDeleteNotice({ type: "success", text: `重新入库任务已提交：${successPayload.task_id || "-"}，状态 ${formatTaskStatus(successPayload.status)}。` });
      await loadDocuments(selectedKnowledgeBase.id);
      await loadIngestionTasks(selectedKnowledgeBase.id);
      await loadDocumentCounts(knowledgeBases);
    } catch (error) {
      if (error instanceof AuthError) { handleAuthAwareError(error, adminMessages.knowledgeBases.chunkFailed); return; }
      setDeleteNotice({ type: "error", text: error instanceof Error ? error.message : adminMessages.knowledgeBases.chunkFailed });
    } finally {
      setChunkingSource("");
    }
  }

  async function handleRetryIngestionTask(task: IngestionTaskResponse) {
    if (!selectedKnowledgeBase) return;
    setRetryingTaskId(task.id);
    setDeleteNotice(null);
    try {
      const response = await authFetch(`${apiBaseUrl}/ingestion/tasks/${encodeURIComponent(task.id)}/retry`, {
        method: "POST",
      });
      const payload = (await response.json()) as IngestionTaskResponse | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "重试入库任务失败。",
        );
      }
      setDeleteNotice({ type: "success", text: `重试任务已提交：${task.filename || task.source || task.id}。` });
      await loadDocuments(selectedKnowledgeBase.id);
      await loadIngestionTasks(selectedKnowledgeBase.id);
      await loadDocumentCounts(knowledgeBases);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "重试入库任务失败。");
        return;
      }
      setDeleteNotice({
        type: "error",
        text: error instanceof Error ? error.message : "重试入库任务失败。",
      });
    } finally {
      setRetryingTaskId("");
    }
  }

  async function handleCancelIngestionTask(task: IngestionTaskResponse) {
    if (!selectedKnowledgeBase) return;
    setCancellingTaskId(task.id);
    setDeleteNotice(null);
    try {
      const response = await authFetch(`${apiBaseUrl}/ingestion/tasks/${encodeURIComponent(task.id)}/cancel`, {
        method: "POST",
      });
      const payload = (await response.json()) as IngestionTaskResponse | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "取消入库任务失败。",
        );
      }
      setDeleteNotice({ type: "success", text: `入库任务已取消：${task.filename || task.source || task.id}。` });
      await loadDocuments(selectedKnowledgeBase.id);
      await loadIngestionTasks(selectedKnowledgeBase.id);
      await loadDocumentCounts(knowledgeBases);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, "取消入库任务失败。");
        return;
      }
      setDeleteNotice({
        type: "error",
        text: error instanceof Error ? error.message : "取消入库任务失败。",
      });
    } finally {
      setCancellingTaskId("");
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
            : adminMessages.documents.deleteFailed,
        );
      }

      const successPayload = payload as DeleteDocumentResponse;
      setDeleteNotice({
        type: "success",
        text: adminMessages.documents.deleteSuccessTemplate
          .replace("{kb_name}", successPayload.knowledge_base_name)
          .replace("{source}", successPayload.source),
      });
      await loadDocuments(selectedKnowledgeBase.id);
      await loadDocumentCounts(knowledgeBases);
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, adminMessages.documents.deleteFailed);
        return;
      }
      setDeleteNotice({
        type: "error",
        text: error instanceof Error ? error.message : adminMessages.documents.deleteFailed,
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
            : adminMessages.sessions.deleteSessionFailed,
        );
      }

      setSessionNotice({
        type: "success",
        text: (payload as DeleteSessionResponse).message,
      });
      await reloadSessions();
    } catch (error) {
      if (error instanceof AuthError) {
        handleAuthAwareError(error, adminMessages.sessions.deleteSessionFailed);
        return;
      }
      setSessionNotice({
        type: "error",
        text: error instanceof Error ? error.message : adminMessages.sessions.deleteSessionFailed,
      });
    } finally {
      setDeletingSessionId("");
    }
  }

  async function fetchStats() {
    const response = await authFetch(`${apiBaseUrl}/admin/stats`);
    if (!response.ok) return;
    setAdminStats((await response.json()) as AdminStats);
  }

  async function fetchUsers(page = 1, pageSize = USER_PAGE_SIZE) {
    const response = await authFetch(
      `${apiBaseUrl}/admin/users?page=${page}&page_size=${pageSize}`,
    );
    const payload = (await response.json()) as { users: UserListItem[]; total: number } | { detail?: string };
    if (!response.ok) {
      throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : adminMessages.users.fetchFailed);
    }
    const data = payload as { users: UserListItem[]; total: number };
    setUsers(data.users);
    setUserTotal(data.total);
  }

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = newUsername.trim();
    if (!trimmedName || !newPassword) {
      setUserNotice({ type: "error", text: adminMessages.forms.credentialsRequired });
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
        throw new Error("detail" in payload && typeof payload.detail === "string" ? payload.detail : adminMessages.users.createFailed);
      }
      const created = payload as UserListItem;
      setUserNotice({ type: "success", text: adminMessages.users.createSuccessTemplate.replace("{username}", created.username) });
      setNewUsername("");
      setNewPassword("");
      setNewRole("user");
      await fetchUsers(userPage, USER_PAGE_SIZE);
    } catch (error) {
      if (error instanceof AuthError) { handleAuthAwareError(error, adminMessages.users.createFailed); return; }
      setUserNotice({ type: "error", text: error instanceof Error ? error.message : adminMessages.users.createFailed });
    } finally {
      setCreatingUser(false);
    }
  }

  async function handleDeleteUser(userId: string, username: string) {
    if (!window.confirm(adminMessages.users.confirmDelete.replace("{username}", username))) return;
    setDeletingUserId(userId);
    setUserNotice(null);
    try {
      const response = await authFetch(`${apiBaseUrl}/admin/users/${userId}`, { method: "DELETE" });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail || adminMessages.users.deleteFailed);
      }
      setUserNotice({ type: "success", text: adminMessages.users.deleteSuccessTemplate.replace("{username}", username) });
      await fetchUsers(userPage, USER_PAGE_SIZE);
    } catch (error) {
      if (error instanceof AuthError) { handleAuthAwareError(error, adminMessages.users.deleteFailed); return; }
      setUserNotice({ type: "error", text: error instanceof Error ? error.message : adminMessages.users.deleteFailed });
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
          <p className={styles.emptyState}>{adminMessages.overview.loading}</p>
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
            placeholder={adminMessages.search.placeholder}
            aria-label={adminMessages.search.ariaLabel}
          />
          {searchOpen && knowledgeBaseQuery.trim() ? (
            <div className={styles.searchMenu}>
              <div className={styles.searchGroup}>
                <p className={styles.searchGroupLabel}>{adminMessages.search.groupKnowledgeBases}</p>
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
                  <p className={styles.searchEmpty}>{adminMessages.search.noMatchKnowledgeBases}</p>
                ) : null}
              </div>

              <div className={styles.searchGroup}>
                <p className={styles.searchGroupLabel}>{adminMessages.search.groupDocuments}</p>
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
                  <p className={styles.searchEmpty}>{adminMessages.search.searching}</p>
                ) : null}
                {!searchLoading && !searchDocuments.length ? (
                  <p className={styles.searchEmpty}>{adminMessages.search.noMatchDocuments}</p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
        <div className={styles.headerActions}>
          <Link className={styles.secondaryLink} href="/">
            {adminMessages.sidebar.backToChat}
          </Link>
          <div className={styles.adminIdentity}>
            <span className={styles.adminAvatar}>
              {(currentUser?.username || "A").slice(0, 1).toUpperCase()}
            </span>
            <span>
              <span className={styles.adminUserName}>{currentUser?.username}</span>
              <span className={styles.adminUserRole}>{adminMessages.sidebar.adminRole}</span>
            </span>
          </div>
        </div>
      </header>

      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>M</span>
          <span>
            <strong>{adminMessages.brand.adminPanel}</strong>
            <small>{adminMessages.brand.console}</small>
          </span>
        </div>

        <p className={styles.navLabel}>{adminMessages.sidebar.navLabel}</p>
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
            <span>{adminMessages.sidebar.adminAccount}</span>
          </div>
          <button className={styles.sidebarLogout} onClick={handleLogout} type="button">
            {adminMessages.sidebar.logout}
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
              {activeView === "overview" ? (
                <button className={styles.refreshButton} disabled={statsRefreshing} onClick={async () => { setStatsRefreshing(true); try { await Promise.all([loadHealth(), loadDocumentCounts(knowledgeBases), reloadSessions(), fetchStats()]); } finally { setStatsRefreshing(false); } }} type="button">
                  {statsRefreshing ? "刷新中..." : "刷新统计"}
                </button>
              ) : null}
            </div>
          </div>

          {activeView === "overview" ? (
            <>
              <section className={styles.summaryGrid}>
                <OverviewMetric icon="layers" label="知识库" value={String(knowledgeBases.length)} />
                <OverviewMetric icon="doc" label="文档总数" value={String(adminStats?.documents.total ?? totalDocumentCount)} />
                <OverviewMetric icon="chat" label="聊天会话" value={String(sessions.length)} />
                <OverviewMetric icon="people" label="用户数" value={String(adminStats?.users ?? "-")} />
              </section>

              <section className={styles.summaryGrid} style={{ marginTop: 16 }}>
                <OverviewMetric icon="grid" label="向量总数" value={adminStats ? String(adminStats.milvus.vectors) : "-"} />
                <OverviewMetric icon="upload" label="存储用量" value={adminStats ? `${(adminStats.documents.size / 1024).toFixed(1)} KB` : "-"} />
                <OverviewMetric icon="grid" label="服务状态" value={health === "ok" ? "正常" : health} />
                <OverviewMetric icon="layers" label="Milvus 集合数" value={adminStats ? String(adminStats.milvus.collections) : "-"} />
              </section>

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
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    {docLoading ? <span className={styles.helper}>加载中...</span> : null}
                    <button className={styles.primaryButton} style={{ minHeight: 38, padding: "0 16px", fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }} onClick={() => setUploadModalOpen(true)} type="button">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                      上传文档
                    </button>
                  </div>
                </div>

                {uploadNotice ? <NoticeBox notice={uploadNotice} /> : null}

                <Modal
                  open={uploadModalOpen}
                  title="上传文档"
                  subtitle="选择文件上传到当前知识库，支持 .txt .md .pdf .docx"
                  onClose={() => { if (!uploadLoading) { setUploadModalOpen(false); setSelectedFile(null); } }}
                  actions={
                    <>
                      <button className={styles.backButton} disabled={uploadLoading} onClick={() => { setUploadModalOpen(false); setSelectedFile(null); }} type="button">取消</button>
                      <button className={styles.primaryButton} disabled={uploadLoading || !selectedFile} onClick={() => { void handleUpload(); }} type="button">
                        {uploadLoading ? "上传中..." : "上传"}
                      </button>
                    </>
                  }
                >
                  <label className={styles.fileDropZone} htmlFor="upload-file-input">
                    <input id="upload-file-input" type="file" accept=".txt,.md,.pdf,.docx" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} style={{ display: "none" }} />
                    {selectedFile ? (
                      <span>{selectedFile.name}（{(selectedFile.size / 1024).toFixed(1)} KB）</span>
                    ) : (
                      <span>点击选择文件，或将文件拖拽到此处</span>
                    )}
                  </label>
                </Modal>

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
                          <td className={styles.documentName}>
                            <button className={styles.knowledgeBaseLink} onClick={() => void viewChunks(document.source, document.filename)} type="button">
                              {document.filename}
                            </button>
                          </td>
                          <td>{document.file_type}</td>
                          <td>
                            <span className={styles.statusBadge}>
                              {formatDocumentStatus(document.status)}
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
                            <button className={styles.refreshButton} style={{ marginRight: 6, minHeight: 32, padding: "4px 10px", fontSize: 12 }} disabled={chunkingSource === document.source} onClick={() => void handleChunkDocument(document.source)} type="button">
                              {chunkingSource === document.source ? "提交中..." : "重新入库"}
                            </button>
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

                <div className={styles.statusList}>
                  <div className={styles.cardHeader} style={{ borderBottom: "none", minHeight: 48 }}>
                    <div>
                      <h3 className={styles.cardTitle}>最近入库任务</h3>
                      <p className={styles.cardSubtitle}>查看上传、解析、向量入库的节点执行日志</p>
                    </div>
                    <button
                      className={styles.refreshButton}
                      disabled={taskLoading || !selectedKnowledgeBase}
                      onClick={() => selectedKnowledgeBase && void loadIngestionTasks(selectedKnowledgeBase.id)}
                      style={{ marginTop: 0 }}
                      type="button"
                    >
                      {taskLoading ? "刷新中..." : "刷新任务"}
                    </button>
                  </div>

                  {ingestionTasks.length ? (
                    <div className={styles.sessionLayout} style={{ marginTop: 8 }}>
                      <div className={styles.sessionTableWrap}>
                        <table className={styles.table}>
                          <thead>
                            <tr>
                              <th>任务</th>
                              <th>类型</th>
                              <th>状态</th>
                              <th>操作</th>
                              <th>Chunks</th>
                              <th>创建时间</th>
                            </tr>
                          </thead>
                          <tbody>
                            {ingestionTasks.map((task) => (
                              <tr key={task.id} className={task.id === selectedTask?.id ? styles.activeRow : ""}>
                                <td>
                                  <button className={styles.sessionSelectButton} onClick={() => setSelectedTaskId(task.id)} type="button">
                                    {task.filename || task.source || task.id}
                                  </button>
                                </td>
                                <td>{formatTaskType(task.task_type)}</td>
                                <td><span className={styles.statusBadge}>{formatTaskStatus(task.status)}</span></td>
                                <td>
                                  {isLiveIngestionStatus(task.status) ? (
                                    <button
                                      className={styles.deleteButton}
                                      disabled={cancellingTaskId === task.id}
                                      onClick={() => void handleCancelIngestionTask(task)}
                                      style={{ minHeight: 32, padding: "4px 10px", fontSize: 12 }}
                                      type="button"
                                    >
                                      {cancellingTaskId === task.id ? "取消中..." : "取消"}
                                    </button>
                                  ) : task.status === "failed" ? (
                                    <button
                                      className={styles.refreshButton}
                                      disabled={retryingTaskId === task.id}
                                      onClick={() => void handleRetryIngestionTask(task)}
                                      style={{ marginTop: 0, minHeight: 32, padding: "4px 10px", fontSize: 12 }}
                                      type="button"
                                    >
                                      {retryingTaskId === task.id ? "提交中..." : "重试"}
                                    </button>
                                  ) : (
                                    <span className={styles.helper}>-</span>
                                  )}
                                </td>
                                <td>{task.chunks}{task.skipped ? ` / 跳过 ${task.skipped}` : ""}</td>
                                <td>{new Date(task.created_at).toLocaleString("zh-CN")}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      <div className={styles.messageViewer}>
                        <div className={styles.cardHeader} style={{ borderBottom: "none", minHeight: 32 }}>
                          <h3 className={styles.viewerTitle}>{selectedTask ? `${selectedTask.filename || selectedTask.source} 的节点日志` : "节点日志"}</h3>
                          {selectedTask && isLiveIngestionStatus(selectedTask.status) ? (
                            <button
                              className={styles.deleteButton}
                              disabled={cancellingTaskId === selectedTask.id}
                              onClick={() => void handleCancelIngestionTask(selectedTask)}
                              style={{ minHeight: 32, padding: "4px 10px", fontSize: 12 }}
                              type="button"
                            >
                              {cancellingTaskId === selectedTask.id ? "取消中..." : "取消任务"}
                            </button>
                          ) : selectedTask?.status === "failed" ? (
                            <button
                              className={styles.refreshButton}
                              disabled={retryingTaskId === selectedTask.id}
                              onClick={() => void handleRetryIngestionTask(selectedTask)}
                              style={{ marginTop: 0, minHeight: 32, padding: "4px 10px", fontSize: 12 }}
                              type="button"
                            >
                              {retryingTaskId === selectedTask.id ? "提交中..." : "重试任务"}
                            </button>
                          ) : null}
                        </div>
                        {selectedTask ? (
                          <div className={styles.messageList}>
                            <div className={styles.messageMeta}>
                              <span>状态：{formatTaskStatus(selectedTask.status)}</span>
                              <span>当前节点：{selectedTask.current_node || "-"}</span>
                              <span>消息：{selectedTask.message || "-"}</span>
                            </div>
                            {buildTaskTimeline(selectedTask).map((item) => (
                              <article key={item.key} className={styles.messageCard}>
                                <div className={styles.messageCardHeader}>
                                  <strong>{formatNodeName(item.nodeName)}</strong>
                                  <span>{formatTaskStatus(item.status)} · {item.durationMs}ms</span>
                                </div>
                                <p className={styles.messageContent}>{item.message || "-"}</p>
                                {item.startedAt || item.finishedAt ? (
                                  <div className={styles.messageMeta}>
                                    {item.startedAt ? <span>开始：{new Date(item.startedAt).toLocaleTimeString("zh-CN")}</span> : null}
                                    {item.finishedAt ? <span>结束：{new Date(item.finishedAt).toLocaleTimeString("zh-CN")}</span> : null}
                                  </div>
                                ) : null}
                                {item.error ? <p className={styles.noticeError} style={{ marginTop: 8 }}>{item.error}</p> : null}
                                {item.details ? (
                                  <pre className={styles.taskDetails}>
                                    {JSON.stringify(item.details, null, 2)}
                                  </pre>
                                ) : null}
                              </article>
                            ))}
                          </div>
                        ) : (
                          <p className={styles.emptyState}>选择一个任务后，这里会显示节点日志。</p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className={styles.emptyState}>当前知识库还没有入库任务。</p>
                  )}
                </div>
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
                          {editingKbId === item.id ? (
                            <input
                              className={styles.input}
                              value={editKbName}
                              onChange={(e) => setEditKbName(e.target.value)}
                              onKeyDown={(e) => { if (e.key === "Enter") void handleRenameKnowledgeBase(item.id); if (e.key === "Escape") { setEditingKbId(""); setEditKbName(""); } }}
                              autoFocus
                            />
                          ) : (
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
                          )}
                        </td>
                        <td>{item.collection_name}</td>
                        <td>{item.embedding_model || "-"}</td>
                        <td>{item.document_count}</td>
                        <td>{new Date(item.created_at).toLocaleString("zh-CN")}</td>
                        <td>
                          {editingKbId === item.id ? (
                            <>
                              <button className={styles.primaryButton} style={{ marginRight: 6, minHeight: 32, padding: "4px 10px", fontSize: 12 }} disabled={renamingKb} onClick={() => void handleRenameKnowledgeBase(item.id)} type="button">
                                {renamingKb ? "保存中..." : "保存"}
                              </button>
                              <button className={styles.refreshButton} style={{ minHeight: 32, padding: "4px 10px", fontSize: 12 }} onClick={() => { setEditingKbId(""); setEditKbName(""); }} type="button">取消</button>
                            </>
                          ) : (
                            <>
                              <button className={styles.refreshButton} style={{ marginRight: 6, minHeight: 32, padding: "4px 10px", fontSize: 12 }} onClick={() => { setEditingKbId(item.id); setEditKbName(item.name); }} type="button">编辑</button>
                              <button className={styles.deleteButton} disabled={deletingKnowledgeBaseId === item.id} onClick={() => void handleDeleteKnowledgeBase(item)} type="button">
                                {deletingKnowledgeBaseId === item.id ? "删除中..." : "删除"}
                              </button>
                            </>
                          )}
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

          {activeView === "retrieval-test" ? (
            <section className={styles.card}>
              <div className={styles.cardHeader}>
                <div>
                  <h3 className={styles.cardTitle}>检索测试</h3>
                  <p className={styles.cardSubtitle}>输入问题，查看知识库召回片段、来源和分数。</p>
                </div>
              </div>

              <form className={styles.form} onSubmit={handleRetrievalTest}>
                <label className={styles.label} htmlFor="retrieval-kb">知识库</label>
                <Select
                  id="retrieval-kb"
                  value={retrievalKbId}
                  onChange={setRetrievalKbId}
                  options={knowledgeBases.map((item) => ({
                    value: item.id,
                    label: `${item.name} (${item.document_count} 个文档)`,
                  }))}
                  placeholder="请选择知识库..."
                />

                <label className={styles.label} htmlFor="retrieval-question">测试问题</label>
                <textarea
                  id="retrieval-question"
                  className={styles.input}
                  value={retrievalQuestion}
                  onChange={(event) => setRetrievalQuestion(event.target.value)}
                  placeholder="输入要测试召回效果的问题..."
                  rows={4}
                  style={{ resize: "vertical", minHeight: 96 }}
                />

                <label className={styles.label} htmlFor="retrieval-top-k">召回片段数</label>
                <input
                  id="retrieval-top-k"
                  className={styles.input}
                  max={20}
                  min={1}
                  onChange={(event) => setRetrievalTopK(Number(event.target.value) || 6)}
                  type="number"
                  value={retrievalTopK}
                />

                <label className={styles.checkboxLabel}>
                  <input
                    checked={retrievalUseRerank}
                    onChange={(event) => setRetrievalUseRerank(event.target.checked)}
                    type="checkbox"
                  />
                  启用 Rerank 重排
                </label>

                <div>
                  <button className={styles.primaryButton} disabled={retrievalLoading} type="submit">
                    {retrievalLoading ? "测试中..." : "开始测试"}
                  </button>
                </div>
              </form>

              {retrievalNotice ? <NoticeBox notice={retrievalNotice} /> : null}

              {retrievalResult ? (
                <section className={styles.statusList}>
                  <div className={styles.statusRow}>
                    <span className={styles.statusLabel}>检索范围</span>
                    <span className={styles.statusValue}>{retrievalResult.knowledge_base_names.join("、")}</span>
                  </div>
                  <div className={styles.statusRow}>
                    <span className={styles.statusLabel}>耗时 / 命中</span>
                    <span className={styles.statusValue}>
                      {retrievalResult.duration_ms}ms / {retrievalResult.source_count} 个片段
                      {retrievalResult.candidate_count ? ` / ${retrievalResult.candidate_count} 个候选` : ""}
                    </span>
                  </div>
                  <div className={styles.statusRow}>
                    <span className={styles.statusLabel}>Rerank</span>
                    <span className={styles.statusValue}>
                      {retrievalResult.rerank_enabled
                        ? retrievalResult.rerank_applied
                          ? "已应用"
                          : `未应用${retrievalResult.rerank_error ? `：${retrievalResult.rerank_error}` : ""}`
                        : "未启用"}
                    </span>
                  </div>

                  {retrievalResult.sources.length ? (
                    retrievalResult.sources.map((source, index) => (
                      <article className={styles.messageCard} key={`${source.source || "source"}-${index}`}>
                        <div className={styles.messageCardHeader}>
                          <strong>片段 {index + 1} · {formatRetrievalType(source.retrieval_type)}</strong>
                          <span>score {formatScore(source.score)}</span>
                        </div>
                        <div className={styles.messageMeta}>
                          <span>vector: {formatScore(source.vector_score)}</span>
                          <span>keyword: {formatScore(source.keyword_score)}</span>
                          <span>rerank: {formatScore(source.rerank_score)}</span>
                          <span>source: {source.source || "-"}</span>
                        </div>
                        <p className={styles.messageContent} style={{ marginTop: 10 }}>
                          {source.content}
                        </p>
                      </article>
                    ))
                  ) : (
                    <p className={styles.emptyState}>没有召回到片段，可以尝试换个问题或检查文档是否已入库。</p>
                  )}
                </section>
              ) : null}
            </section>
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
                <Select
                  id="new-role"
                  value={newRole}
                  onChange={(v) => setNewRole(v as "user" | "admin")}
                  options={[
                    { value: "user", label: "普通用户 (user)" },
                    { value: "admin", label: "管理员 (admin)" },
                  ]}
                  placeholder="请选择角色..."
                />
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
      <Modal
        open={createKnowledgeBaseOpen}
        title="创建知识库"
        subtitle="创建一个新的知识库，用于存储、向量化和检索文档。"
        onClose={() => { setCreateKnowledgeBaseOpen(false); setKnowledgeBaseNotice(null); }}
        onSubmit={handleCreateKnowledgeBase}
        actions={
          <>
            <button className={styles.backButton} onClick={() => { setCreateKnowledgeBaseOpen(false); setKnowledgeBaseNotice(null); }} type="button">取消</button>
            <button className={styles.primaryButton} disabled={creatingKnowledgeBase} type="submit">{creatingKnowledgeBase ? "创建中..." : "创建"}</button>
          </>
        }
      >
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
              <Select
                id="kb-embedding-model"
                required
                value={newEmbeddingModel}
                onChange={setNewEmbeddingModel}
                options={[
                  { value: "text-embedding-v4", label: "text-embedding-v4 (通义千问)" },
                  { value: "text-embedding-v3", label: "text-embedding-v3 (通义千问)" },
                ]}
                placeholder="请选择 Embedding 模型..."
              />
              <p className={styles.helperText}>用于将文档内容转换为向量，不同模型影响检索精度</p>

              {knowledgeBaseNotice ? <NoticeBox notice={knowledgeBaseNotice} /> : null}
      </Modal>
      <Modal
        open={chunkDetailOpen}
        title={`片段详情：${chunkDetailDoc}`}
        onClose={() => setChunkDetailOpen(false)}
        actions={<button className={styles.backButton} onClick={() => setChunkDetailOpen(false)} type="button">关闭</button>}
      >
        {chunkLoading ? (
          <p className={styles.emptyState}>加载中...</p>
        ) : chunkItems.length > 0 ? (
          <div style={{ maxHeight: "460px", overflowY: "auto", display: "grid", gap: 10 }}>
            {chunkItems.map((chunk, idx) => (
              <div key={chunk.id || idx} style={{ padding: 12, border: "1px solid var(--card-border)", borderRadius: 7, background: "var(--panel-alt)", fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                <span style={{ color: "var(--helper)", fontSize: 11, fontWeight: 700 }}>片段 {idx + 1}</span>
                <p style={{ margin: "6px 0 0", color: "var(--body)" }}>{chunk.text}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className={styles.emptyState}>暂无片段数据，请先等待入库完成或点击重新入库。</p>
        )}
      </Modal>
    </main>
  );
}

function Bar({ label, value, max, color, bg }: { label: string; value: number; max: number; color: string; bg: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ flex: 1, minWidth: 100, padding: "10px 12px", borderRadius: 7, background: bg }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12, fontWeight: 600, color }}>
        <span>{label}</span><span>{value}</span>
      </div>
      <div style={{ height: 8, borderRadius: 4, background: "#e2e8f0", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, borderRadius: 4, background: color, transition: "width 0.4s" }} />
      </div>
      <div style={{ marginTop: 4, fontSize: 10, color: "var(--helper)" }}>{pct}%</div>
    </div>
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

type TaskLog = IngestionTaskResponse["logs"][number];

type TaskTimelineItem = {
  key: string;
  nodeName: string;
  status: string;
  message: string;
  details: Record<string, unknown> | null;
  error: string | null;
  durationMs: number;
  startedAt?: string | null;
  finishedAt?: string | null;
};

function buildTaskTimeline(task: IngestionTaskResponse): TaskTimelineItem[] {
  const grouped = new Map<string, TaskLog[]>();
  for (const log of task.logs) {
    const logs = grouped.get(log.node_name) ?? [];
    logs.push(log);
    grouped.set(log.node_name, logs);
  }

  return Array.from(grouped.entries()).map(([nodeName, logs]) => {
    const finishedLog =
      [...logs].reverse().find((log) => log.status !== "running") ?? logs[logs.length - 1];
    const runningLog = logs.find((log) => log.status === "running");
    const detailsLog = [...logs].reverse().find((log) => log.details);
    const errorLog = [...logs].reverse().find((log) => log.error);

    return {
      key: `${nodeName}-${logs[0]?.id ?? nodeName}`,
      nodeName,
      status: finishedLog?.status ?? "running",
      message: finishedLog?.message || runningLog?.message || "",
      details: detailsLog?.details ?? null,
      error: errorLog?.error ?? null,
      durationMs: finishedLog?.duration_ms ?? 0,
      startedAt: runningLog?.started_at ?? finishedLog?.started_at ?? null,
      finishedAt: finishedLog?.finished_at ?? null,
    };
  });
}

function formatDocumentStatus(status: string) {
  return (
    {
      pending: "待入库",
      queued: "队列中",
      running: "入库中",
      retrying: "重试中",
      success: "已入库",
      failed: "入库失败",
      cancelled: "已取消",
      indexed: "已入库",
    }[status] || status
  );
}

function formatScore(score?: number | null) {
  if (typeof score !== "number") {
    return "-";
  }
  return score.toFixed(3);
}

function formatRetrievalType(type?: string | null) {
  return (
    {
      vector: "向量召回",
      keyword: "关键词召回",
      hybrid: "混合召回",
    }[type || ""] || type || "-"
  );
}

function isLiveIngestionStatus(status: string) {
  return LIVE_INGESTION_STATUSES.has(status);
}

function formatTaskType(type: string) {
  return (
    {
      upload: "上传入库",
      register: "本地登记",
      chunk: "重新入库",
    }[type] || type
  );
}

function formatNodeName(nodeName: string) {
  return (
    {
      enqueue: "提交队列",
      read_upload: "读取上传",
      store_file: "保存文件",
      record_document: "登记文档",
      prepare_indexing: "准备入库",
      inspect_document: "检查文档",
      chunk_embed_index: "生成片段与向量入库",
      update_document_record: "更新文档记录",
      finalize_task: "完成任务",
    }[nodeName] || nodeName
  );
}

function formatTaskStatus(status: string) {
  return (
    {
      pending: "待执行",
      queued: "队列中",
      running: "执行中",
      retrying: "重试中",
      success: "成功",
      failed: "失败",
      cancelled: "已取消",
      skipped: "跳过",
    }[status] || status
  );
}
