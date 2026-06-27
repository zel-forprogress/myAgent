import type { FormEvent, ReactNode } from "react";

type ModalProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
  onSubmit?: (e: FormEvent<HTMLFormElement>) => void;
};

export function Modal({
  open,
  title,
  subtitle,
  children,
  actions,
  onClose,
  onSubmit,
}: ModalProps) {
  if (!open) return null;

  const labelId = title.replace(/\s+/g, "-").toLowerCase();

  return (
    <div className="modalOverlay" role="presentation">
      <div aria-labelledby={labelId} aria-modal="true" className="modal" role="dialog">
        <div className="modalHeader">
          <div>
            <h3 className="modalTitle" id={labelId}>{title}</h3>
            {subtitle ? <p className="modalSubtitle">{subtitle}</p> : null}
          </div>
          <button aria-label="关闭弹窗" className="modalCloseButton" onClick={onClose} type="button">×</button>
        </div>

        {onSubmit ? (
          <form className="modalForm" onSubmit={onSubmit}>
            {children}
            {actions ? <div className="modalActions">{actions}</div> : null}
          </form>
        ) : (
          <div className="modalForm">
            {children}
            {actions ? <div className="modalActions">{actions}</div> : null}
          </div>
        )}
      </div>
    </div>
  );
}
