import { useQuestionnaire } from '../../../context/QuestionnaireContext'
import { PROPERTY_TYPE_OPTIONS } from '../../../constants/options'
import StepLayout from '../StepLayout'
import FormField from '../../shared/FormField'
import OptionCards from '../../shared/OptionCards'
import ToggleSwitch from '../../shared/ToggleSwitch'

export default function Step1Housing() {
  const { formData, updateHardFilters } = useQuestionnaire()
  const { property_type, has_yard } = formData.hard_filters

  return (
    <StepLayout
      title="Tell us about your home"
      subtitle="This helps us rule out breeds that wouldn't be comfortable in your space."
    >
      <FormField label="What type of home do you live in?">
        <OptionCards
          name="property_type"
          options={PROPERTY_TYPE_OPTIONS}
          value={property_type}
          onChange={(value) => updateHardFilters({ property_type: value })}
        />
      </FormField>

      <FormField label="Do you have access to a yard?">
        <ToggleSwitch
          label="I have a yard"
          checked={has_yard}
          onChange={(checked) => updateHardFilters({ has_yard: checked })}
        />
      </FormField>
    </StepLayout>
  )
}
