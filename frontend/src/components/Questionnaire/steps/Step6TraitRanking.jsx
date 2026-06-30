import { useState } from 'react'
import { useQuestionnaire } from '../../../context/QuestionnaireContext'
import { TRAITS } from '../../../constants/options'
import StepLayout from '../StepLayout'
import styles from './Step6TraitRanking.module.css'

export default function Step6TraitRanking() {
  const { formData, setTraitPriorityRanking } = useQuestionnaire()
  const ranking = formData.trait_priority_ranking
  const [draggedKey, setDraggedKey] = useState(null)

  const traitsByKey = Object.fromEntries(TRAITS.map((trait) => [trait.key, trait]))

  function moveTrait(key, direction) {
    const index = ranking.indexOf(key)
    const targetIndex = index + direction
    if (targetIndex < 0 || targetIndex >= ranking.length) return

    const next = [...ranking]
    ;[next[index], next[targetIndex]] = [next[targetIndex], next[index]]
    setTraitPriorityRanking(next)
  }

  function handleDrop(targetKey) {
    if (!draggedKey || draggedKey === targetKey) {
      setDraggedKey(null)
      return
    }
    const next = ranking.filter((key) => key !== draggedKey)
    const targetIndex = next.indexOf(targetKey)
    next.splice(targetIndex, 0, draggedKey)
    setTraitPriorityRanking(next)
    setDraggedKey(null)
  }

  return (
    <StepLayout
      title="Rank what matters most to you"
      subtitle="Drag to reorder, or use the arrows. Put the trait you care about most at the top."
    >
      <ol className={styles.list}>
        {ranking.map((key, index) => {
          const trait = traitsByKey[key]
          return (
            <li
              key={key}
              className={`${styles.item} ${draggedKey === key ? styles.dragging : ''}`}
              draggable
              onDragStart={() => setDraggedKey(key)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => handleDrop(key)}
              onDragEnd={() => setDraggedKey(null)}
            >
              <span className={styles.rank}>{index + 1}</span>
              <span className={styles.handle} aria-hidden="true">
                ⠿
              </span>
              <span className={styles.text}>
                <span className={styles.traitLabel}>{trait.label}</span>
                <span className={styles.traitDescription}>{trait.description}</span>
              </span>
              <span className={styles.arrows}>
                <button
                  type="button"
                  className={styles.arrowButton}
                  onClick={() => moveTrait(key, -1)}
                  disabled={index === 0}
                  aria-label={`Move ${trait.label} up`}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className={styles.arrowButton}
                  onClick={() => moveTrait(key, 1)}
                  disabled={index === ranking.length - 1}
                  aria-label={`Move ${trait.label} down`}
                >
                  ↓
                </button>
              </span>
            </li>
          )
        })}
      </ol>
    </StepLayout>
  )
}
