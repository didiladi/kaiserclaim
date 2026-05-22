interface Props {
  initials: string;
  color: string;
  size?: number;
}

export function Avatar({ initials, color, size = 36 }: Props) {
  const fontSize = Math.round(size * 0.33);
  return (
    <div
      className="flex items-center justify-center rounded-full flex-shrink-0 font-bold"
      style={{
        width: size,
        height: size,
        backgroundColor: color + "18",
        color,
        fontSize,
      }}
    >
      {initials}
    </div>
  );
}
