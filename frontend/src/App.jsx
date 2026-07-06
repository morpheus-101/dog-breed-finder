import { useState } from 'react'
import { Route, Routes, useNavigate } from 'react-router-dom'
import { QuestionnaireProvider, useQuestionnaire } from './context/QuestionnaireContext'
import { fetchRecommendations } from './api/recommend'
import Questionnaire from './components/Questionnaire/Questionnaire'
import LoadingState from './components/Loading/LoadingState'
import ResultsPage from './components/Results/ResultsPage'
import ErrorState from './components/Results/ErrorState'
import BreedDetailPage from './components/BreedDetail/BreedDetailPage'
import styles from './App.module.css'

// view: 'questionnaire' | 'loading' | 'results' | 'error'
function AppContent() {
  const { resetFormData } = useQuestionnaire()
  const navigate = useNavigate()
  const [view, setView] = useState('questionnaire')
  const [results, setResults] = useState([])
  const [emptyMessage, setEmptyMessage] = useState('')
  const [lastSubmittedData, setLastSubmittedData] = useState(null)
  const [isRateLimited, setIsRateLimited] = useState(false)

  async function submitQuestionnaire(formData) {
    setLastSubmittedData(formData)
    setView('loading')
    try {
      const data = await fetchRecommendations(formData)
      setResults(data.results)
      setEmptyMessage(data.message || '')
      setView('results')
    } catch (err) {
      setIsRateLimited(err.message === 'rate_limited')
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
    setIsRateLimited(false)
    setView('questionnaire')
    navigate('/')
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
        <Routes>
          <Route
            path="/"
            element={
              <>
                {view === 'questionnaire' && <Questionnaire onSubmit={submitQuestionnaire} />}
                {view === 'loading' && <LoadingState />}
                {view === 'results' && (
                  <ResultsPage
                    results={results}
                    message={emptyMessage}
                    onAdjustAnswers={adjustAnswers}
                  />
                )}
                {view === 'error' && (
                  <ErrorState onRetry={retry} rateLimited={isRateLimited} />
                )}
              </>
            }
          />
          <Route path="/breed/:breedName" element={<BreedDetailPage />} />
        </Routes>
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
