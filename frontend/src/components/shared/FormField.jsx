import styles from './FormField.module.css'

export default function FormField({ label, hint, children }) {
  return (
    <div className={styles.field}>
      <span className={styles.label}>{label}</span>
      {hint && <span className={styles.hint}>{hint}</span>}
      <div className={styles.control}>{children}</div>
    </div>
  )
}
