export default function StatusBadge({ label, tone = "cyan" }) {
  const tones = {
    cyan: "text-[#3ec7ff] border-[#3ec7ff]/40 bg-[#3ec7ff]/10",
    red: "text-[#ff6b6b] border-[#ff6b6b]/40 bg-[#ff6b6b]/10",
    amber: "text-[#f0c14b] border-[#f0c14b]/40 bg-[#f0c14b]/10",
    green: "text-[#5dcc8a] border-[#5dcc8a]/40 bg-[#5dcc8a]/10",
    mute: "text-ops-300 border-white/15 bg-white/5",
  };

  return (
    <span className={`inline-flex items-center gap-1.5 border px-1.5 py-[2px] text-[10px] font-medium tracking-wide ${tones[tone] || tones.mute}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}
