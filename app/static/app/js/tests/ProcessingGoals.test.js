import ProcessingGoals, { CUSTOM_GOAL_ID } from '../classes/ProcessingGoals';

const presets = [
  { id: 1, name: 'Default', options: [] },
  { id: 2, name: 'Fast Orthophoto', options: [] },
  { id: 3, name: 'High Resolution', options: [] },
  { id: 4, name: 'LS6 Small', options: [] }
];

describe('ProcessingGoals', () => {
  it('maps installed presets to cards and always keeps the custom card last', () => {
    const cards = ProcessingGoals.resolve(presets);
    const ids = cards.map(c => c.id);
    expect(ids).toEqual(['ortho-fast', 'standard', 'high-res', CUSTOM_GOAL_ID]);
    expect(cards[0].preset.id).toBe(2);
    expect(cards[cards.length - 1].preset).toBeNull();
  });

  it('hides cards whose preset is not installed', () => {
    const cards = ProcessingGoals.resolve([{ id: 9, name: 'Default', options: [] }]);
    expect(cards.map(c => c.id)).toEqual(['standard', CUSTOM_GOAL_ID]);
  });

  it('copes with no presets at all', () => {
    expect(ProcessingGoals.resolve(null).map(c => c.id)).toEqual([CUSTOM_GOAL_ID]);
  });

  it('exposes titles and help as translatable functions', () => {
    const card = ProcessingGoals.findById('terrain');
    expect(typeof card.title()).toBe('string');
    expect(card.presetName).toBe('DSM + DTM');
    expect(ProcessingGoals.findById(CUSTOM_GOAL_ID).presetName).toBeNull();
    expect(ProcessingGoals.findById('nope')).toBeNull();
  });
});
