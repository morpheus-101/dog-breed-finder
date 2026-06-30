import styles from './OptionCards.module.css'

// Renders a row of selectable cards. Works as a single-select radio group.
export default function OptionCards({ options, value, onChange, name }) {
  return (
    <div className={styles.group} role="radiogroup" aria-label={name}>
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            className={`${styles.card} ${selected ? styles.selected : ''}`}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
