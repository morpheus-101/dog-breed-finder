import styles from './SliderField.module.css'

export default function SliderField({ min, max, step = 1, value, onChange, formatValue }) {
  return (
    <div className={styles.wrapper}>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className={styles.slider}
      />
      <span className={styles.value}>{formatValue ? formatValue(value) : value}</span>
    </div>
  )
}
