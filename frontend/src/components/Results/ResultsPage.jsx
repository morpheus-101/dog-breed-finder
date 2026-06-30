import BreedCard from './BreedCard'
import EmptyResults from './EmptyResults'
import styles from './ResultsPage.module.css'

export default function ResultsPage({ results, message, onAdjustAnswers }) {
  if (results.length === 0) {
    return <EmptyResults message={message} onAdjustAnswers={onAdjustAnswers} />
  }

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <h2>Your best matches</h2>
        <p className={styles.subtitle}>
          Ranked from best to worst fit based on everything you told us.
        </p>
      </header>

      <div className={styles.grid}>
        {results.map((breed) => (
          <BreedCard key={breed.breed_name} breed={breed} />
        ))}
      </div>

      <button type="button" className={styles.adjustButton} onClick={onAdjustAnswers}>
        Adjust my answers
      </button>
    </div>
  )
}
