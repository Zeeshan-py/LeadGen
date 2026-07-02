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

export const businessTypes = [
  "Accountants", "Auto Repair", "Construction", "Dentists", "Electricians",
  "Gyms", "HVAC", "Law Firms", "Marketing Agencies", "Medical Clinics",
  "Plumbers", "Real Estate", "Restaurants", "Roofing", "Salons and Spas",
];
