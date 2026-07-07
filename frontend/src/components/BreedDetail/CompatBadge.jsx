import styles from './BreedDetailPage.module.css'

export default function CompatBadge({ label, value }) {
  const known = value === 0 || value === 1
  const good = value === 1
  const variant = known ? (good ? styles.badgeGood : styles.badgeBad) : styles.badgeUnknown

  return (
    <span className={`${styles.badge} ${variant}`}>
      <span aria-hidden="true">{known ? (good ? '✓' : '✕') : '?'}</span>
      {label}
    </span>
  )
}
