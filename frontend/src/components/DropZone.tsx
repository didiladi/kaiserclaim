import { useRef, useState, DragEvent } from "react";
import { Camera } from "lucide-react";
import clsx from "clsx";

interface Props {
  onFile: (file: File) => void;
  accept?: string;
}

export function DropZone({ onFile, accept = "image/*,.pdf" }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={clsx(
        "flex flex-col items-center gap-3 p-10 rounded-lg border-2 border-dashed cursor-pointer transition-colors",
        dragging
          ? "border-kc-accent bg-kc-accentLight"
          : "border-kc-border bg-kc-surfaceAlt hover:border-kc-accent"
      )}
    >
      <div className="w-14 h-14 rounded-lg bg-kc-accentMid flex items-center justify-center">
        <Camera className="text-kc-accent" size={28} />
      </div>
      <div className="text-center">
        <p className="text-[15px] font-semibold text-kc-text">Foto aufnehmen oder Datei wählen</p>
        <p className="text-[13px] text-kc-textSec mt-1">Beleg fotografieren oder PDF hochladen</p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
        }}
      />
    </div>
  );
}
