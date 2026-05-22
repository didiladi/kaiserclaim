import { ReactNode, InputHTMLAttributes } from "react";
import clsx from "clsx";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  leftIcon?: ReactNode;
}

export function Input({ label, error, leftIcon, className, ...rest }: Props) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-[13px] font-semibold text-kc-textSec">{label}</label>
      )}
      <div className="relative">
        {leftIcon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-kc-textTri pointer-events-none">
            {leftIcon}
          </div>
        )}
        <input
          className={clsx(
            "w-full h-12 bg-kc-surfaceAlt rounded-md border border-transparent px-3.5 text-[15px] text-kc-text",
            "focus:outline-none focus:border-kc-accent placeholder:text-kc-textTri transition-colors",
            error && "border-kc-danger",
            leftIcon && "pl-10",
            className
          )}
          {...rest}
        />
      </div>
      {error && <p className="text-xs text-kc-danger">{error}</p>}
    </div>
  );
}
