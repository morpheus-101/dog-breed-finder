import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchBreed } from '../../api/breed'
import StatBar from './StatBar'
import CompatBadge from './CompatBadge'
import styles from './BreedDetailPage.module.css'

const PERSONALITY_TRAITS = [
  { key: 'energy_level', label: 'Energy level' },
  { key: 'affection_level', label: 'Affection' },
  { key: 'playfulness', label: 'Playfulness' },
  { key: 'intelligence', label: 'Intelligence' },
  { key: 'independence', label: 'Independence' },
  { key: 'trainability', label: 'Trainability' },
  { key: 'barking_level', label: 'Barking level' },
  { key: 'protective_instinct', label: 'Protective instinct' },
  { key: 'separation_anxiety', label: 'Separation anxiety' },
  { key: 'shedding_level', label: 'Shedding' },
]

const COMPATIBILITY = [
  { key: 'good_with_kids', label: 'Kids' },
  { key: 'good_with_dogs', label: 'Other dogs' },
  { key: 'good_with_cats', label: 'Cats' },
  { key: 'good_with_elderly', label: 'Elderly family members' },
]

const SUITABILITY = [
  { key: 'apartment_suitable', label: 'Apartment living' },
  { key: 'urban_suitable', label: 'Urban environments' },
  { key: 'needs_yard', label: 'Needs a yard' },
  { key: 'first_time_owner_suitable', label: 'First-time owners' },
  { key: 'guard_dog', label: 'Guard dog' },
  { key: 'working_dog', label: 'Working / herding breed' },
]

export default function BreedDetailPage() {
  const { breedName } = useParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState('loading')
  const [breed, setBreed] = useState(null)
  const [imageFailed, setImageFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setImageFailed(false)

    fetchBreed(breedName)
      .then((data) => {
        if (cancelled) return
        setBreed(data)
        setStatus('ready')
      })
      .catch((err) => {
        if (cancelled) return
        setStatus(err.message === 'not_found' ? 'not_found' : 'error')
      })

    return () => {
      cancelled = true
    }
  }, [breedName])

  if (status === 'loading') {
    return (
      <div className={styles.statusWrapper}>
        <div className={styles.spinner} aria-hidden="true" />
        <p className={styles.text}>Fetching everything we know about {breedName}...</p>
      </div>
    )
  }

  if (status === 'not_found') {
    return (
      <div className={styles.statusWrapper}>
        <div className={styles.icon} aria-hidden="true">
          🐾
        </div>
        <h2>We couldn&apos;t find that breed</h2>
        <p className={styles.text}>It may have been renamed or is no longer in our database.</p>
        <button type="button" className={styles.backButton} onClick={() => navigate(-1)}>
          ← Back to results
        </button>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className={styles.statusWrapper}>
        <div className={styles.icon} aria-hidden="true">
          🐕
        </div>
        <h2>Something went wrong</h2>
        <p className={styles.text}>
          We had trouble loading this breed&apos;s profile. Please try again.
        </p>
        <button type="button" className={styles.backButton} onClick={() => navigate(-1)}>
          ← Back to results
        </button>
      </div>
    )
  }

  const imageUrl = breed.image_url_1 || breed.image_url_2
  const showImage = imageUrl && !imageFailed

  return (
    <div className={styles.wrapper}>
      <button type="button" className={styles.backButton} onClick={() => navigate(-1)}>
        ← Back to results
      </button>

      <section className={styles.hero}>
        <div className={styles.heroImageWrapper}>
          {showImage ? (
            <img
              src={imageUrl}
              alt={breed.breed_name}
              className={styles.heroImage}
              onError={() => setImageFailed(true)}
            />
          ) : (
            <div className={styles.heroImageFallback} aria-hidden="true">
              🐶
            </div>
          )}
        </div>
        <div className={styles.heroText}>
          <h1>{breed.breed_name}</h1>
          <p className={styles.heroMeta}>
            {[breed.akc_group, breed.origin_country].filter(Boolean).join(' · ') ||
              'Origin details not documented'}
          </p>
          {breed.popularity_rank != null && (
            <p className={styles.heroRank}>AKC popularity rank: #{breed.popularity_rank}</p>
          )}
        </div>
      </section>

      <section className={styles.section}>
        <h2>At a glance</h2>
        <dl className={styles.factGrid}>
          <Fact label="Size" value={capitalize(breed.size_category)} />
          <Fact
            label="Lifespan"
            value={rangeText(breed.life_expectancy_min, breed.life_expectancy_max, 'yrs')}
          />
          <Fact label="Weight" value={rangeText(breed.weight_min_kg, breed.weight_max_kg, 'kg')} />
          <Fact label="Height" value={rangeText(breed.height_min_cm, breed.height_max_cm, 'cm')} />
          <Fact label="Coat type" value={breed.coat_type} />
          <Fact label="Hypoallergenic" value={breed.hypoallergenic ? 'Yes' : 'No'} />
        </dl>
      </section>

      <section className={styles.section}>
        <h2>Personality</h2>
        <div className={styles.bars}>
          {PERSONALITY_TRAITS.map(({ key, label }) => (
            <StatBar key={key} label={label} value={breed[key]} />
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2>Compatibility</h2>
        <div className={styles.badges}>
          {COMPATIBILITY.map(({ key, label }) => (
            <CompatBadge key={key} label={label} value={breed[key]} />
          ))}
        </div>
        <div className={styles.bars}>
          <StatBar label="Friendliness with strangers" value={breed.good_with_strangers} />
        </div>
      </section>

      <section className={styles.section}>
        <h2>Suitability</h2>
        <div className={styles.badges}>
          {SUITABILITY.map(({ key, label }) => (
            <CompatBadge key={key} label={label} value={breed[key]} />
          ))}
        </div>
        <div className={styles.bars}>
          <StatBar label="Heat tolerance" value={breed.heat_tolerance} />
          <StatBar label="Cold tolerance" value={breed.cold_tolerance} />
          <StatBar label="Experience required" value={breed.experience_required} />
        </div>
      </section>

      <section className={styles.section}>
        <h2>Care requirements</h2>
        <dl className={styles.factGrid}>
          <Fact label="Grooming frequency" value={scoreText(breed.grooming_frequency)} />
          <Fact label="Grooming cost" value={tierText(breed.grooming_cost_tier)} />
          <Fact
            label="Exercise needed"
            value={breed.exercise_min_per_day != null ? `${breed.exercise_min_per_day} min/day` : null}
          />
          <Fact
            label="Monthly food cost"
            value={breed.monthly_food_cost_usd != null ? `$${breed.monthly_food_cost_usd}/mo` : null}
          />
          <Fact label="Vet cost" value={tierText(breed.vet_cost_tier)} />
          <Fact
            label="Total monthly cost"
            value={breed.monthly_total_cost_usd != null ? `$${breed.monthly_total_cost_usd}/mo` : null}
          />
        </dl>
      </section>

      {breed.llm_summary && (
        <section className={styles.section}>
          <h2>About the {breed.breed_name}</h2>
          <p className={styles.summary}>{breed.llm_summary}</p>
        </section>
      )}
    </div>
  )
}

function Fact({ label, value }) {
  return (
    <div className={styles.fact}>
      <dt>{label}</dt>
      <dd>{value ?? 'Not documented'}</dd>
    </div>
  )
}

function capitalize(text) {
  if (!text) return null
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function rangeText(min, max, unit) {
  if (min == null && max == null) return null
  if (min == null) return `Up to ${max} ${unit}`
  if (max == null) return `From ${min} ${unit}`
  if (min === max) return `${min} ${unit}`
  return `${min}–${max} ${unit}`
}

function tierText(tier) {
  if (tier == null) return null
  const labels = { 1: 'Low', 2: 'Moderate', 3: 'High' }
  return labels[tier] || `Tier ${tier}`
}

function scoreText(score) {
  if (score == null) return null
  return `${score} / 5`
}
