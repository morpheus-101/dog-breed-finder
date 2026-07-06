import styles from './BreedDetailPage.module.css'

export default function StatBar({ label, value }) {
  const hasValue = typeof value === 'number'
  const pct = hasValue ? (value / 5) * 100 : 0

  return (
    <div className={styles.statBar}>
      <div className={styles.statBarHeader}>
        <span>{label}</span>
        <span>{hasValue ? `${value} / 5` : 'N/A'}</span>
      </div>
      <div className={styles.statBarTrack}>
        <div className={styles.statBarFill} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
