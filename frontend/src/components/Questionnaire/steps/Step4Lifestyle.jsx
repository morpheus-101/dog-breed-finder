import { useQuestionnaire } from '../../../context/QuestionnaireContext'
import { CLIMATE_OPTIONS, LEVEL_OPTIONS, PRIMARY_PURPOSE_OPTIONS } from '../../../constants/options'
import StepLayout from '../StepLayout'
import FormField from '../../shared/FormField'
import OptionCards from '../../shared/OptionCards'
import SliderField from '../../shared/SliderField'
import ToggleSwitch from '../../shared/ToggleSwitch'

export default function Step4Lifestyle() {
  const { formData, updateSoftContext } = useQuestionnaire()
  const {
    daily_time_available_min,
    climate,
    outdoor_time_expected,
    grooming_commitment,
    primary_purpose,
    prioritize_longevity,
    prioritize_low_vet_costs,
  } = formData.soft_context

  return (
    <StepLayout
      title="Your day-to-day lifestyle"
      subtitle="This context helps us write explanations that actually fit your life."
    >
      <FormField label="What's the main reason you want a dog?">
        <OptionCards
          name="primary_purpose"
          options={PRIMARY_PURPOSE_OPTIONS}
          value={primary_purpose}
          onChange={(value) => updateSoftContext({ primary_purpose: value })}
        />
      </FormField>

      <FormField label="Time available with your dog each day">
        <SliderField
          min={15}
          max={240}
          step={15}
          value={daily_time_available_min}
          onChange={(value) => updateSoftContext({ daily_time_available_min: value })}
          formatValue={(value) => `${value} min`}
        />
      </FormField>

      <FormField label="What's your climate like?">
        <OptionCards
          name="climate"
          options={CLIMATE_OPTIONS}
          value={climate}
          onChange={(value) => updateSoftContext({ climate: value })}
        />
      </FormField>

      <FormField label="How much outdoor time do you expect to give your dog?">
        <OptionCards
          name="outdoor_time_expected"
          options={LEVEL_OPTIONS}
          value={outdoor_time_expected}
          onChange={(value) => updateSoftContext({ outdoor_time_expected: value })}
        />
      </FormField>

      <FormField label="How much grooming are you willing to commit to?">
        <OptionCards
          name="grooming_commitment"
          options={LEVEL_OPTIONS}
          value={grooming_commitment}
          onChange={(value) => updateSoftContext({ grooming_commitment: value })}
        />
      </FormField>

      <FormField label="A couple more preferences">
        <ToggleSwitch
          label="Long lifespan matters to me"
          checked={prioritize_longevity}
          onChange={(checked) => updateSoftContext({ prioritize_longevity: checked })}
        />
        <ToggleSwitch
          label="Low vet costs matter to me"
          checked={prioritize_low_vet_costs}
          onChange={(checked) => updateSoftContext({ prioritize_low_vet_costs: checked })}
        />
      </FormField>
    </StepLayout>
  )
}
