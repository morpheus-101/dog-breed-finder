import styles from './BreedCountIndicator.module.css'

export default function BreedCountIndicator({ count, total }) {
  // Nothing fetched yet (still waiting on the first debounced call) — render
  // nothing rather than a misleading placeholder.
  if (count === null) return null

  const isZero = count === 0

  return (
    <div
      className={`${styles.wrapper} ${isZero ? styles.warning : ''}`}
      aria-live="polite"
    >
      {isZero ? (
        <span>
          No breeds match your current filters — consider loosening some requirements
        </span>
      ) : (
        <span>
          <strong>{count}</strong> of {total} breeds match your criteria so far
        </span>
      )}
    </div>
  )
}
