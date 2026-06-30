import { useState } from 'react'
import { QuestionnaireProvider, useQuestionnaire } from './context/QuestionnaireContext'
import { fetchRecommendations } from './api/recommend'
import Questionnaire from './components/Questionnaire/Questionnaire'
import LoadingState from './components/Loading/LoadingState'
import ResultsPage from './components/Results/ResultsPage'
import ErrorState from './components/Results/ErrorState'
import styles from './App.module.css'

// view: 'questionnaire' | 'loading' | 'results' | 'error'
function AppContent() {
  const { resetFormData } = useQuestionnaire()
  const [view, setView] = useState('questionnaire')
  const [results, setResults] = useState([])
  const [emptyMessage, setEmptyMessage] = useState('')
  const [lastSubmittedData, setLastSubmittedData] = useState(null)

  async function submitQuestionnaire(formData) {
    setLastSubmittedData(formData)
    setView('loading')
    try {
      const data = await fetchRecommendations(formData)
      setResults(data.results)
      setEmptyMessage(data.message || '')
      setView('results')
    } catch {
      setView('error')
    }
  }

  function retry() {
    if (lastSubmittedData) {
      submitQuestionnaire(lastSubmittedData)
    } else {
      setView('questionnaire')
    }
  }

  function adjustAnswers() {
    setView('questionnaire')
  }

  function startOver() {
    resetFormData()
    setResults([])
    setEmptyMessage('')
    setLastSubmittedData(null)
    setView('questionnaire')
  }

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <button type="button" className={styles.logo} onClick={startOver}>
          🐾 PawMatch
        </button>
        <p className={styles.tagline}>Find the dog breed that fits your life</p>
      </header>

      <main className={styles.main}>
        {view === 'questionnaire' && <Questionnaire onSubmit={submitQuestionnaire} />}
        {view === 'loading' && <LoadingState />}
        {view === 'results' && (
          <ResultsPage
            results={results}
            message={emptyMessage}
            onAdjustAnswers={adjustAnswers}
          />
        )}
        {view === 'error' && <ErrorState onRetry={retry} />}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <QuestionnaireProvider>
      <AppContent />
    </QuestionnaireProvider>
  )
}
