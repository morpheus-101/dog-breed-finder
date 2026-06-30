import { createContext, useContext, useMemo, useState } from 'react'
import { defaultFormData } from '../constants/defaultFormData'

const QuestionnaireContext = createContext(null)

export function QuestionnaireProvider({ children }) {
  const [formData, setFormData] = useState(defaultFormData)

  const updateHardFilters = (updates) =>
    setFormData((prev) => ({
      ...prev,
      hard_filters: { ...prev.hard_filters, ...updates },
    }))

  const updateSoftContext = (updates) =>
    setFormData((prev) => ({
      ...prev,
      soft_context: { ...prev.soft_context, ...updates },
    }))

  const setTraitPriorityRanking = (ranking) =>
    setFormData((prev) => ({ ...prev, trait_priority_ranking: ranking }))

  const resetFormData = () => setFormData(defaultFormData)

  const value = useMemo(
    () => ({
      formData,
      updateHardFilters,
      updateSoftContext,
      setTraitPriorityRanking,
      resetFormData,
    }),
    [formData],
  )

  return (
    <QuestionnaireContext.Provider value={value}>
      {children}
    </QuestionnaireContext.Provider>
  )
}

export function useQuestionnaire() {
  const context = useContext(QuestionnaireContext)
  if (!context) {
    throw new Error('useQuestionnaire must be used within a QuestionnaireProvider')
  }
  return context
}
