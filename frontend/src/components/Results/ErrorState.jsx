import styles from './StatusMessage.module.css'

export default function ErrorState({ onRetry }) {
  return (
    <div className={styles.wrapper}>
      <div className={styles.icon} aria-hidden="true">
        🐕
      </div>
      <h2>Something went wrong</h2>
      <p className={styles.text}>
        We had trouble finding your matches. Please check your connection and try
        again.
      </p>
      <button type="button" className={styles.primaryButton} onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}
