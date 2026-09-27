export default function Brand({ className = '' }: { className?: string }) {
  return <svg className={className} viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <path d="m20 3 14 8v17l-14 9-14-9V11L20 3Z" stroke="#6b65ff" strokeWidth="2" />
    <path d="m20 9 10 6v11l-10 6-10-6V15l10-6Z" fill="#20275b" stroke="#20d5eb" />
    <path d="m14 20 4 4 8-9" stroke="#8ff6ff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    {[[20, 3], [34, 11], [34, 28], [20, 37], [6, 28], [6, 11]].map(([cx, cy]) =>
      <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.6" fill={cy % 2 ? '#22d3ee' : '#8b70ff'} />)}
  </svg>
}
