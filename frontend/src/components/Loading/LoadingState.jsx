import styles from './LoadingState.module.css'

export default function LoadingState() {
  return (
    <div className={styles.wrapper}>
      <div className={styles.spinner} aria-hidden="true">
        🐾
      </div>
      <h2 className={styles.title}>Sniffing out your matches…</h2>
      <p className={styles.subtitle}>
        We're comparing your answers against hundreds of breeds. This usually takes
        just a few seconds.
      </p>
    </div>
  )
}
