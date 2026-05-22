import { ReactNode } from "react";
import clsx from "clsx";
import { Loader } from "lucide-react";

interface Props {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "secondary" | "danger";
  size?: "sm" | "md" | "lg";
  fullWidth?: boolean;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  size = "md",
  fullWidth,
  disabled,
  loading,
  className,
}: Props) {
  const base = "inline-flex items-center justify-center gap-2 font-semibold rounded-md transition-all active:scale-97 disabled:opacity-50 disabled:cursor-not-allowed";

  const sizeClass = {
    sm: "h-9 px-4 text-sm",
    md: "h-11 px-5 text-sm",
    lg: "h-[52px] px-6 text-base",
  }[size];

  const variantClass = {
    primary: "bg-kc-accent text-white hover:bg-kc-accentHover",
    secondary: "bg-kc-surfaceAlt text-kc-text hover:bg-kc-border",
    danger: "bg-kc-dangerBg text-kc-danger hover:opacity-80",
  }[variant];

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={clsx(base, sizeClass, variantClass, fullWidth && "w-full", className)}
    >
      {loading ? <Loader className="animate-kcSpin" size={16} /> : null}
      {children}
    </button>
  );
}
