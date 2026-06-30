import styles from './ProgressBar.module.css'

export default function ProgressBar({ currentStep, totalSteps, stepTitle }) {
  const percent = (currentStep / totalSteps) * 100

  return (
    <div className={styles.wrapper}>
      <div className={styles.track}>
        <div className={styles.fill} style={{ width: `${percent}%` }} />
      </div>
      <span className={styles.label}>
        Step {currentStep} of {totalSteps} — {stepTitle}
      </span>
    </div>
  )
}
