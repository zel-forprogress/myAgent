"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./page.module.css";
import { apiBaseUrl, LoginResponse } from "../../lib/api";
import { getStoredAuth, setStoredAuth } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123456");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const auth = getStoredAuth();
    if (auth) {
      router.replace("/");
    }
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${apiBaseUrl}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      });

      const payload = (await response.json()) as LoginResponse | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload && typeof payload.detail === "string"
            ? payload.detail
            : "登录失败。",
        );
      }

      const successPayload = payload as LoginResponse;
      setStoredAuth(successPayload);
      router.replace("/");
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "登录失败。",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <div className={styles.header}>
          <p className={styles.eyebrow}>myAgent / Login</p>
          <h1 className={styles.title}>登录知识库 Agent</h1>
          <p className={styles.subtitle}>
            先登录，再进入聊天页或管理后台。当前开发环境默认内置测试账号。
          </p>
        </div>

        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.label} htmlFor="username">
            用户名
          </label>
          <input
            id="username"
            className={styles.input}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="请输入用户名"
          />

          <label className={styles.label} htmlFor="password">
            密码
          </label>
          <input
            id="password"
            className={styles.input}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="请输入密码"
          />

          <button className={styles.submitButton} disabled={loading} type="submit">
            {loading ? "登录中..." : "登录"}
          </button>

          {error ? <p className={styles.error}>{error}</p> : null}
        </form>

        <div className={styles.tips}>
          <div className={styles.tipCard}>
            <strong>测试账号</strong>
            <span>账号：admin</span>
            <span>密码：admin123456</span>
          </div>
          <div className={styles.tipCard}>
            <strong>测试账号</strong>
            <span>账号：demo</span>
            <span>密码：demo123456</span>
          </div>
        </div>
      </section>
    </main>
  );
}
