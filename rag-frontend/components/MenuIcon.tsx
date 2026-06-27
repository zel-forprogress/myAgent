export type MenuIconVariant =
  | "grid"
  | "layers"
  | "upload"
  | "path"
  | "doc"
  | "chat"
  | "people";

export function MenuIcon({ variant }: { variant: MenuIconVariant }) {
  if (variant === "grid") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4" y="4" width="6" height="6" rx="1.5" />
        <rect x="14" y="4" width="6" height="6" rx="1.5" />
        <rect x="4" y="14" width="6" height="6" rx="1.5" />
        <rect x="14" y="14" width="6" height="6" rx="1.5" />
      </svg>
    );
  }

  if (variant === "layers") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 4l8 4-8 4-8-4z" />
        <path d="M4 12l8 4 8-4" />
        <path d="M4 16l8 4 8-4" />
      </svg>
    );
  }

  if (variant === "upload") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 16V6" />
        <path d="M8 10l4-4 4 4" />
        <path d="M5 19h14" />
      </svg>
    );
  }

  if (variant === "path") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 7h7l2 3h7" />
        <path d="M6 17h12" />
        <circle cx="7" cy="17" r="1.5" />
        <circle cx="17" cy="17" r="1.5" />
      </svg>
    );
  }

  if (variant === "doc") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8 3h6l5 5v13H8z" />
        <path d="M14 3v5h5" />
        <path d="M10 13h7" />
        <path d="M10 17h7" />
      </svg>
    );
  }

  if (variant === "people") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
        <circle cx="19" cy="7" r="2.5" />
        <path d="M15 18c0-2.2 1.6-4.1 3.6-4.8" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 8a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3h-4l-4 3v-3H8a3 3 0 0 1-3-3z" />
      <circle cx="9" cy="10.5" r="1" />
      <circle cx="12" cy="10.5" r="1" />
      <circle cx="15" cy="10.5" r="1" />
    </svg>
  );
}
