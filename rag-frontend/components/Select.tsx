import * as RadixSelect from "@radix-ui/react-select";
import type { ReactNode } from "react";
import { MenuIcon, type MenuIconVariant } from "./MenuIcon";

type SelectOption = { value: string; label: string; icon?: MenuIconVariant };

type SelectProps = {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  required?: boolean;
  id?: string;
};

export function Select({ value, onChange, options, placeholder = "请选择...", required, id }: SelectProps) {
  const selected = options.find((o) => o.value === value);

  return (
    <RadixSelect.Root value={value || undefined} onValueChange={onChange} required={required}>
      <RadixSelect.Trigger id={id} className="radix-select-trigger">
        <RadixSelect.Value>
          {selected ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              {selected.icon ? <MenuIcon variant={selected.icon} /> : null}
              {selected.label}
            </span>
          ) : (
            <span style={{ color: "var(--helper)" }}>{placeholder}</span>
          )}
        </RadixSelect.Value>
        <RadixSelect.Icon className="radix-select-icon">
          <ChevronDown />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>

      <RadixSelect.Portal>
        <RadixSelect.Content className="radix-select-content" position="popper" sideOffset={4}>
          <RadixSelect.Viewport className="radix-select-viewport">
            {options.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.icon ? <MenuIcon variant={opt.icon} /> : null}
                {opt.label}
              </SelectItem>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}

function SelectItem({ value, children }: { value: string; children: ReactNode }) {
  return (
    <RadixSelect.Item value={value} className="radix-select-item">
      <RadixSelect.ItemText>{children}</RadixSelect.ItemText>
      <RadixSelect.ItemIndicator className="radix-select-item-indicator">
        <CheckIcon />
      </RadixSelect.ItemIndicator>
    </RadixSelect.Item>
  );
}

function ChevronDown() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M2 4l4 4 4-4" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M2 7l3.5 3.5L12 4" />
    </svg>
  );
}
