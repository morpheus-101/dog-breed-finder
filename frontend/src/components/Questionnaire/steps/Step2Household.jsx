import { useQuestionnaire } from '../../../context/QuestionnaireContext'
import StepLayout from '../StepLayout'
import FormField from '../../shared/FormField'
import ToggleSwitch from '../../shared/ToggleSwitch'

export default function Step2Household() {
  const { formData, updateHardFilters } = useQuestionnaire()
  const { has_kids, has_elderly, has_other_dogs, has_cats, has_allergies } =
    formData.hard_filters

  return (
    <StepLayout
      title="Who else is in the household?"
      subtitle="Some breeds are a better fit for certain families than others."
    >
      <FormField label="Who will the dog be living with?">
        <ToggleSwitch
          label="Kids in the home"
          checked={has_kids}
          onChange={(checked) => updateHardFilters({ has_kids: checked })}
        />
        <ToggleSwitch
          label="Elderly family members"
          checked={has_elderly}
          onChange={(checked) => updateHardFilters({ has_elderly: checked })}
        />
        <ToggleSwitch
          label="Other dogs"
          checked={has_other_dogs}
          onChange={(checked) => updateHardFilters({ has_other_dogs: checked })}
        />
        <ToggleSwitch
          label="Cats"
          checked={has_cats}
          onChange={(checked) => updateHardFilters({ has_cats: checked })}
        />
      </FormField>

      <FormField label="Allergies" hint="We'll only suggest hypoallergenic breeds.">
        <ToggleSwitch
          label="Someone in the household has dog allergies"
          checked={has_allergies}
          onChange={(checked) => updateHardFilters({ has_allergies: checked })}
        />
      </FormField>
    </StepLayout>
  )
}
