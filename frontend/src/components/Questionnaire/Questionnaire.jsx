import { useEffect, useRef, useState } from 'react'
import { useQuestionnaire } from '../../context/QuestionnaireContext'
import { fetchFilterCount } from '../../api/filterCount'
import ProgressBar from './ProgressBar'
import BreedCountIndicator from './BreedCountIndicator'
import Step1Housing from './steps/Step1Housing'
import Step2Household from './steps/Step2Household'
import Step3BudgetExperience from './steps/Step3BudgetExperience'
import Step4Lifestyle from './steps/Step4Lifestyle'
import Step5Preferences from './steps/Step5Preferences'
import Step6TraitRanking from './steps/Step6TraitRanking'
import styles from './Questionnaire.module.css'

const STEPS = [
  { title: 'Housing', Component: Step1Housing },
  { title: 'Household', Component: Step2Household },
  { title: 'Budget & Experience', Component: Step3BudgetExperience },
  { title: 'Lifestyle', Component: Step4Lifestyle },
  { title: 'Preferences', Component: Step5Preferences },
  { title: 'Trait Ranking', Component: Step6TraitRanking },
]

const ALLOWED_TRAITS = new Set([
  'energy_level',
  'trainability',
  'barking_level',
  'affection_level',
  'protective_instinct',
  'shedding_level',
])

function isValidTraitRanking(ranking) {
  return (
    Array.isArray(ranking) &&
    ranking.length === 6 &&
    new Set(ranking).size === 6 &&
    ranking.every((trait) => ALLOWED_TRAITS.has(trait))
  )
}

export default function Questionnaire({ onSubmit }) {
  const { formData } = useQuestionnaire()
  const [stepIndex, setStepIndex] = useState(0)
  const [breedCount, setBreedCount] = useState(null)
  const [totalBreeds, setTotalBreeds] = useState(null)
  const debounceRef = useRef(null)

  const isFirstStep = stepIndex === 0
  const isLastStep = stepIndex === STEPS.length - 1
  const { Component } = STEPS[stepIndex]

  const { hard_filters } = formData

  // Debounced so a slider drag (e.g. monthly budget) doesn't fire a request
  // per pixel — only after the user pauses. Keeps the previous count visible
  // while the new one loads, and fails silently (count just stays stale) so a
  // hiccup here never blocks the questionnaire.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    debounceRef.current = setTimeout(() => {
      fetchFilterCount(hard_filters)
        .then((data) => {
          setBreedCount(data.breed_count)
          setTotalBreeds(data.total_breeds_considered)
        })
        .catch(() => {
          // Keep showing the last known count rather than an error.
        })
    }, 300)

    return () => clearTimeout(debounceRef.current)
  }, [hard_filters])

  function goNext() {
    if (isLastStep) {
      if (!isValidTraitRanking(formData.trait_priority_ranking)) {
        // Defensive client-side guard; the drag-and-rank UI should never produce
        // an invalid ranking, but the API contract requires us to check before submit.
        window.alert(
          'Something went wrong with your trait ranking. Please reorder the traits and try again.',
        )
        return
      }
      onSubmit(formData)
      return
    }
    setStepIndex((index) => Math.min(index + 1, STEPS.length - 1))
  }

  function goBack() {
    setStepIndex((index) => Math.max(index - 1, 0))
  }

  return (
    <div className={styles.wrapper}>
      <ProgressBar
        currentStep={stepIndex + 1}
        totalSteps={STEPS.length}
        stepTitle={STEPS[stepIndex].title}
      />
      <BreedCountIndicator count={breedCount} total={totalBreeds} />

      <Component />

      <div className={styles.nav}>
        <button
          type="button"
          className={styles.backButton}
          onClick={goBack}
          disabled={isFirstStep}
        >
          Back
        </button>
        <button type="button" className={styles.nextButton} onClick={goNext}>
          {isLastStep ? 'Find my matches' : 'Next'}
        </button>
      </div>
    </div>
  )
}
