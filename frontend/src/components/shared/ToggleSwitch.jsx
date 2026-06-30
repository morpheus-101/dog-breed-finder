import styles from './ToggleSwitch.module.css'

export default function ToggleSwitch({ label, checked, onChange, hint }) {
  return (
    <label className={styles.row}>
      <span className={styles.text}>
        <span className={styles.label}>{label}</span>
        {hint && <span className={styles.hint}>{hint}</span>}
      </span>
      <span
        className={`${styles.switch} ${checked ? styles.on : ''}`}
        role="switch"
        aria-checked={checked}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          className={styles.input}
        />
        <span className={styles.knob} />
      </span>
    </label>
  )
}
