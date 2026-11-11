import { groupTaskVersions, urgentVersionState } from '../TaskVersions';

const t = (id, extra = {}) => Object.assign({ id, version: 1, parent_task_ref: null, created_at: "2026-01-01T00:00:00Z" }, extra);
const ids = tasks => tasks.map(x => x.id);

describe('groupTaskVersions', () => {
  it('leaves single tasks unchanged and in order', () => {
    const groups = groupTaskVersions([t("a"), t("b"), t("c")]);
    expect(groups.map(g => ids(g.tasks))).toEqual([["a"], ["b"], ["c"]]);
    expect(groups.map(g => g.head.id)).toEqual(["a", "b", "c"]);
  });

  it('groups a chain v1 -> v2 -> v3 and picks the highest version as head', () => {
    const groups = groupTaskVersions([
      t("v1"), t("v3", { version: 3, parent_task_ref: "v2" }), t("v2", { version: 2, parent_task_ref: "v1" }), t("other")]);
    expect(groups.length).toBe(2);
    const g = groups.find(x => x.rootId === "v1");
    expect(ids(g.tasks)).toEqual(["v3", "v2", "v1"]);
    expect(g.head.id).toBe("v3");
  });

  it('groups branching trees by root, not direct parent', () => {
    const groups = groupTaskVersions([
      t("r"), t("a", { version: 2, parent_task_ref: "r" }), t("b", { version: 3, parent_task_ref: "r" }),
      t("c", { version: 4, parent_task_ref: "a" })]);
    expect(groups.length).toBe(1);
    expect(groups[0].head.id).toBe("c");
    expect(ids(groups[0].tasks)).toEqual(["c", "b", "a", "r"]);
  });

  it('makes an orphan (parent missing from list) the root of its own group', () => {
    const groups = groupTaskVersions([
      t("v2", { version: 2, parent_task_ref: "deleted" }), t("v3", { version: 3, parent_task_ref: "v2" })]);
    expect(groups.length).toBe(1);
    expect(groups[0].rootId).toBe("v2");
    expect(groups[0].head.id).toBe("v3");
  });

  it('survives cycles and self-parents deterministically', () => {
    const cyc = [t("a", { parent_task_ref: "b" }), t("b", { parent_task_ref: "a" }), t("s", { parent_task_ref: "s" })];
    const g1 = groupTaskVersions(cyc);
    expect(g1.map(g => ids(g.tasks).sort())).toEqual([["a", "b"], ["s"]]);
    const g2 = groupTaskVersions(cyc.slice().reverse());
    expect(g2.length).toBe(2);
  });

  it('compares ids as strings', () => {
    const groups = groupTaskVersions([t(1), t(2, { version: 2, parent_task_ref: "1" })]);
    expect(groups.length).toBe(1);
  });

  it('breaks version ties by most recent created_at', () => {
    const groups = groupTaskVersions([
      t("r"), t("old", { version: 2, parent_task_ref: "r", created_at: "2026-01-02T00:00:00Z" }),
      t("new", { version: 2, parent_task_ref: "r", created_at: "2026-01-05T00:00:00Z" })]);
    expect(groups[0].head.id).toBe("new");
  });

  it('orders groups by position of their head (preserves server ordering)', () => {
    const groups = groupTaskVersions([t("x"), t("v2", { version: 2, parent_task_ref: "v1" }), t("v1")]);
    expect(groups.map(g => g.head.id)).toEqual(["x", "v2"]);
  });
});

describe('urgentVersionState', () => {
  it('prefers active over failed, null otherwise', () => {
    expect(urgentVersionState([t("a", { status: 40 }), t("b", { status: 30 }), t("c", { status: 20 })])).toBe("active");
    expect(urgentVersionState([t("a", { status: 10 }), t("b", { status: 30 })])).toBe("active");
    expect(urgentVersionState([t("a", { status: 40 }), t("b", { status: 30 })])).toBe("failed");
    expect(urgentVersionState([t("a", { status: 40, last_error: "boom" })])).toBe("failed");
    expect(urgentVersionState([t("a", { status: 40 })])).toBe(null);
    expect(urgentVersionState([])).toBe(null);
  });
});
