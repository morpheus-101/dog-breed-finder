import styles from './StatusMessage.module.css'

export default function EmptyResults({ message, onAdjustAnswers }) {
  return (
    <div className={styles.wrapper}>
      <div className={styles.icon} aria-hidden="true">
        🐾
      </div>
      <h2>No breeds matched all of your criteria</h2>
      <p className={styles.text}>
        {message ||
          "We couldn't find a breed that fits everything you selected. Try loosening a filter — like your budget or size preference — and we'll try again."}
      </p>
      <button type="button" className={styles.primaryButton} onClick={onAdjustAnswers}>
        Adjust my answers
      </button>
    </div>
  )
}
