export const INITIAL_PRODUCTS = [
  {
    id: 'VFL-01',
    name: 'Vial Filling Line (VFL-01)',
    interventions: [
      'Fallen Vial Recovery',
      'Stopper Adjustment',
      'Needle Replacement',
      'Cleared Jam',
      'Environmental Monitoring',
      'Other (SOP Exception)',
    ],
    batches: ['#VFL-2024-001', '#VFL-2024-002', '#VFL-2024-003'],
  },
  {
    id: 'ASL-02',
    name: 'Ampoule Sealing Line (ASL-02)',
    interventions: [
      'Seal Integrity Check',
      'Broken Ampoule Removal',
      'Flame Adjustment',
      'Environmental Monitoring',
      'Other (SOP Exception)',
    ],
    batches: ['#ASL-2024-001', '#ASL-2024-002', '#ASL-2024-003'],
  },
  {
    id: 'LLL-03',
    name: 'Lyophilization Loading Line (LLL-03)',
    interventions: [
      'Tray Repositioning',
      'Collapsed Vial Removal',
      'Door Seal Inspection',
      'Environmental Monitoring',
      'Temperature Probe Adjustment',
      'Other (SOP Exception)',
    ],
    batches: ['#LLL-2024-001', '#LLL-2024-002', '#LLL-2024-003'],
  },
  {
    id: 'ASM-04',
    name: 'Assembly Line (ASM-04)',
    interventions: [
      'Component Jam Clearance',
      'Sensor Alignment',
      'Manual Assembly Assist',
      'Environmental Monitoring',
      'Other (SOP Exception)',
    ],
    batches: ['#ASM-2024-001', '#ASM-2024-002', '#ASM-2024-003'],
  },
];

export function getProducts() {
  const stored = localStorage.getItem('dheera_products');
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        return parsed;
      }
    } catch (e) {
      return INITIAL_PRODUCTS;
    }
  }
  return INITIAL_PRODUCTS;
}

export function saveProducts(products: typeof INITIAL_PRODUCTS) {
  localStorage.setItem('dheera_products', JSON.stringify(products));
}
