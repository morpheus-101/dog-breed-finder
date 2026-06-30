import { TRAITS } from './options'

// Mirrors the /recommend request body shape exactly (skills/api-contract.md section 2).
export const defaultFormData = {
  hard_filters: {
    has_allergies: false,
    property_type: 'house',
    has_yard: true,
    monthly_budget_usd: 150,
    has_other_dogs: false,
    has_cats: false,
    has_kids: false,
    has_elderly: false,
    owner_experience: 'some',
    noise_tolerance: 'medium',
    max_size_category: 'no_preference',
    size_strict: false,
  },
  soft_context: {
    daily_time_available_min: 60,
    climate: 'temperate',
    outdoor_time_expected: 'medium',
    grooming_commitment: 'medium',
    prioritize_longevity: false,
    prioritize_low_vet_costs: false,
    primary_purpose: 'family_pet',
  },
  trait_priority_ranking: TRAITS.map((trait) => trait.key),
}
