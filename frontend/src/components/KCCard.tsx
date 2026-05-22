import { ReactNode } from "react";
import clsx from "clsx";

interface Props {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
}

export function KCCard({ children, className, hover, onClick }: Props) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        "bg-white border border-kc-border rounded-lg shadow-card",
        hover && "transition-all hover:shadow-md hover:-translate-y-px cursor-pointer",
        onClick && "cursor-pointer",
        className
      )}
    >
      {children}
    </div>
  );
}
