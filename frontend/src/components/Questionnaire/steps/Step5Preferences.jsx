import { useQuestionnaire } from '../../../context/QuestionnaireContext'
import { NOISE_TOLERANCE_OPTIONS, SIZE_CATEGORY_OPTIONS } from '../../../constants/options'
import StepLayout from '../StepLayout'
import FormField from '../../shared/FormField'
import OptionCards from '../../shared/OptionCards'
import ToggleSwitch from '../../shared/ToggleSwitch'

export default function Step5Preferences() {
  const { formData, updateHardFilters } = useQuestionnaire()
  const { noise_tolerance, max_size_category, size_strict } = formData.hard_filters

  return (
    <StepLayout
      title="A few last preferences"
      subtitle="Almost there — just your tolerance for noise and size."
    >
      <FormField label="How much barking can you tolerate?">
        <OptionCards
          name="noise_tolerance"
          options={NOISE_TOLERANCE_OPTIONS}
          value={noise_tolerance}
          onChange={(value) => updateHardFilters({ noise_tolerance: value })}
        />
      </FormField>

      <FormField label="What's the largest size you'd consider?">
        <OptionCards
          name="max_size_category"
          options={SIZE_CATEGORY_OPTIONS}
          value={max_size_category}
          onChange={(value) => updateHardFilters({ max_size_category: value })}
        />
      </FormField>

      {max_size_category !== 'no_preference' && (
        <FormField label="Size strictness">
          <ToggleSwitch
            label="Strictly enforce this size limit"
            hint={
              size_strict
                ? 'We will exclude every breed larger than your selected size.'
                : 'We will treat size as a preference and may still show some larger breeds that score well otherwise.'
            }
            checked={size_strict}
            onChange={(checked) => updateHardFilters({ size_strict: checked })}
          />
        </FormField>
      )}
    </StepLayout>
  )
}
