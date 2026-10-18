export function visibleTacoField(key: string, values: Record<string, unknown>) {
  const fold = values.fold ?? 'accordion'
  if (key === 'panels') return fold !== 'gate'
  if (key === 'allowance') return fold !== 'accordion'
  if (key === 'flap_side') return fold === 'roll'
  return true
}
