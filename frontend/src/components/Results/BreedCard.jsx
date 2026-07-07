import { useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './BreedCard.module.css'

export default function BreedCard({ breed }) {
  const [imageFailed, setImageFailed] = useState(false)
  const { breed_name, rank, match_explanation, image_url, key_stats } = breed
  const showImage = image_url && !imageFailed

  return (
    <Link to={`/breed/${encodeURIComponent(breed_name)}`} className={styles.card}>
      <div className={styles.imageWrapper}>
        {showImage ? (
          <img
            src={image_url}
            alt={breed_name}
            className={styles.image}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className={styles.imageFallback} aria-hidden="true">
            🐶
          </div>
        )}
        <span className={styles.rankBadge}>#{rank}</span>
      </div>

      <div className={styles.body}>
        <h3 className={styles.name}>{breed_name}</h3>
        <p className={styles.explanation}>{match_explanation}</p>

        <dl className={styles.stats}>
          <div className={styles.stat}>
            <dt>Size</dt>
            <dd>{capitalize(key_stats.size_category)}</dd>
          </div>
          <div className={styles.stat}>
            <dt>Energy</dt>
            <dd>{key_stats.energy_level} / 5</dd>
          </div>
          <div className={styles.stat}>
            <dt>Est. cost</dt>
            <dd>${key_stats.monthly_total_cost_usd} / mo</dd>
          </div>
        </dl>
      </div>
    </Link>
  )
}

function capitalize(text) {
  if (!text) return text
  return text.charAt(0).toUpperCase() + text.slice(1)
}
