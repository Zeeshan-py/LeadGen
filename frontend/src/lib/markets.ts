export const countriesByContinent = {
  Africa: ["Algeria", "Egypt", "Ethiopia", "Ghana", "Kenya", "Morocco", "Nigeria", "South Africa", "Tanzania", "Tunisia", "Uganda"],
  Asia: ["Bangladesh", "China", "India", "Indonesia", "Japan", "Malaysia", "Pakistan", "Philippines", "Saudi Arabia", "Singapore", "South Korea", "Thailand", "United Arab Emirates", "Vietnam"],
  Europe: ["Austria", "Belgium", "Denmark", "Finland", "France", "Germany", "Ireland", "Italy", "Netherlands", "Norway", "Poland", "Portugal", "Spain", "Sweden", "Switzerland", "United Kingdom"],
  "North America": ["Canada", "Costa Rica", "Dominican Republic", "Jamaica", "Mexico", "Panama", "United States"],
  Oceania: ["Australia", "Fiji", "New Zealand", "Papua New Guinea"],
  "South America": ["Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador", "Paraguay", "Peru", "Uruguay", "Venezuela"],
} as const;

export type Continent = keyof typeof countriesByContinent;
export const continents = Object.keys(countriesByContinent) as Continent[];

const cityCache = new Map<string, string[]>();
const cityCollator = new Intl.Collator("en", { sensitivity: "base" });

export async function getCitiesForCountry(countryName: string): Promise<string[]> {
  const cached = cityCache.get(countryName);
  if (cached) {
    return cached;
  }

  const { City, Country } = await import("country-state-city");
  const country = Country.getAllCountries().find((item) => item.name === countryName);
  if (!country) {
    return [];
  }

  const cities = Array.from(
    new Set(
      (City.getCitiesOfCountry(country.isoCode) ?? [])
        .map((city) => city.name.trim())
        .filter(Boolean),
    ),
  ).sort(cityCollator.compare);
  cityCache.set(countryName, cities);
  return cities;
}

export const businessTypes = [
  "Accountants", "Auto Repair", "Construction", "Dentists", "Electricians",
  "Gyms", "HVAC", "Law Firms", "Marketing Agencies", "Medical Clinics",
  "Plumbers", "Real Estate", "Restaurants", "Roofing", "Salons and Spas",
];
