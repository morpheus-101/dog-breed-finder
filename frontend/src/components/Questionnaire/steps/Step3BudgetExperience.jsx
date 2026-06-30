import { useQuestionnaire } from '../../../context/QuestionnaireContext'
import { OWNER_EXPERIENCE_OPTIONS } from '../../../constants/options'
import StepLayout from '../StepLayout'
import FormField from '../../shared/FormField'
import OptionCards from '../../shared/OptionCards'
import SliderField from '../../shared/SliderField'

export default function Step3BudgetExperience() {
  const { formData, updateHardFilters } = useQuestionnaire()
  const { monthly_budget_usd, owner_experience } = formData.hard_filters

  return (
    <StepLayout
      title="Budget and experience"
      subtitle="A quick gut-check on what you can comfortably take on."
    >
      <FormField
        label="Monthly budget for your dog"
        hint="Food, grooming, routine vet care — your realistic monthly ceiling."
      >
        <SliderField
          min={20}
          max={400}
          step={10}
          value={monthly_budget_usd}
          onChange={(value) => updateHardFilters({ monthly_budget_usd: value })}
          formatValue={(value) => `$${value} / mo`}
        />
      </FormField>

      <FormField label="How experienced are you with dogs?">
        <OptionCards
          name="owner_experience"
          options={OWNER_EXPERIENCE_OPTIONS}
          value={owner_experience}
          onChange={(value) => updateHardFilters({ owner_experience: value })}
        />
      </FormField>
    </StepLayout>
  )
}
