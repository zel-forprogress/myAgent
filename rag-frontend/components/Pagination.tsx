"use client";

import styles from "./Pagination.module.css";

type PaginationProps = {
  currentPage: number;
  pageSize: number;
  totalItems: number;
  itemLabel?: string;
  onPageChange: (page: number) => void;
};

export function Pagination({
  currentPage,
  pageSize,
  totalItems,
  itemLabel = "条",
  onPageChange,
}: PaginationProps) {
  const totalPages = totalItems > 0 ? Math.ceil(totalItems / pageSize) : 0;
  const safePage = totalPages > 0 ? Math.min(Math.max(currentPage, 1), totalPages) : 0;

  return (
    <nav className={styles.pagination} aria-label="分页导航">
      <span className={styles.summary}>
        共 {totalItems} {itemLabel}
      </span>
      <div className={styles.controls}>
        <button
          className={styles.button}
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
          type="button"
        >
          上一页
        </button>
        <span className={styles.pageIndicator} aria-live="polite">
          {safePage} / {totalPages}
        </span>
        <button
          className={styles.button}
          disabled={safePage === 0 || safePage >= totalPages}
          onClick={() => onPageChange(safePage + 1)}
          type="button"
        >
          下一页
        </button>
      </div>
    </nav>
  );
}
