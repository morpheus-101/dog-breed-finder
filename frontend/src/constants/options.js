// Friendly labels for every enum-like field in the API contract (skills/api-contract.md).
// Raw API values (e.g. "family_pet") should never be shown directly in the UI —
// always look them up here first.

export const PROPERTY_TYPE_OPTIONS = [
  { value: 'house', label: 'House' },
  { value: 'apartment', label: 'Apartment' },
]

export const OWNER_EXPERIENCE_OPTIONS = [
  { value: 'first_time', label: 'First-time owner' },
  { value: 'some', label: 'Some experience' },
  { value: 'experienced', label: 'Very experienced' },
]

export const NOISE_TOLERANCE_OPTIONS = [
  { value: 'low', label: 'Low — I need a quiet dog' },
  { value: 'medium', label: 'Medium — occasional barking is fine' },
  { value: 'high', label: "High — barking doesn't bother me" },
]

export const SIZE_CATEGORY_OPTIONS = [
  { value: 'no_preference', label: 'No preference' },
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
  { value: 'giant', label: 'Giant' },
]

export const CLIMATE_OPTIONS = [
  { value: 'temperate', label: 'Temperate' },
  { value: 'hot', label: 'Hot' },
  { value: 'cold', label: 'Cold' },
  { value: 'varies', label: 'Varies a lot' },
]

export const LEVEL_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

export const PRIMARY_PURPOSE_OPTIONS = [
  { value: 'companionship', label: 'Companionship' },
  { value: 'family_pet', label: 'Family pet' },
  { value: 'guard_protection', label: 'Guard / protection' },
  { value: 'active_sports_partner', label: 'Active sports partner' },
  { value: 'emotional_support', label: 'Emotional support' },
]

// Order here is the default trait_priority_ranking before the user drags anything.
export const TRAITS = [
  {
    key: 'energy_level',
    label: 'Energy Level',
    description: 'How active and energetic you want your dog to be.',
  },
  {
    key: 'trainability',
    label: 'Trainability',
    description: 'How easily the dog learns commands and picks up training.',
  },
  {
    key: 'barking_level',
    label: 'Barking Level',
    description: 'How vocal or quiet you want the breed to be.',
  },
  {
    key: 'affection_level',
    label: 'Affection Level',
    description: 'How affectionate and cuddly the breed is with its family.',
  },
  {
    key: 'protective_instinct',
    label: 'Protective Instinct',
    description: 'How likely the breed is to watch over and guard its home.',
  },
  {
    key: 'shedding_level',
    label: 'Shedding Level',
    description: 'How much the breed sheds and the grooming upkeep involved.',
  },
]

export function labelFor(options, value) {
  return options.find((option) => option.value === value)?.label ?? value
}
