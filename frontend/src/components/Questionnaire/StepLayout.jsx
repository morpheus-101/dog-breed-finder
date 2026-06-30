import styles from './StepLayout.module.css'

export default function StepLayout({ title, subtitle, children }) {
  return (
    <div className={styles.step}>
      <h2 className={styles.title}>{title}</h2>
      {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      <div className={styles.content}>{children}</div>
    </div>
  )
}
