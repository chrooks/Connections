import { EditableGroup } from "../types/admin";

/** Defines the structural shape of a puzzle for validation and editor rendering. */
export interface PuzzleEditorConfig {
  groupCount: number;
  wordsPerGroup: number;
}

/** Classic 4×4 Connections puzzle shape. */
export const CLASSIC_CONFIG: PuzzleEditorConfig = {
  groupCount: 4,
  wordsPerGroup: 4,
};

/** Per-group validation errors. null means no error for that field. */
export interface GroupValidationError {
  categoryName: string | null;
  words: (string | null)[];
}

/**
 * Validates all groups against the given config.
 *
 * Checks:
 * - Category name is non-empty (trimmed)
 * - Each word slot is non-empty (trimmed)
 * - No duplicate words across the entire puzzle (case-insensitive)
 *
 * Returns one GroupValidationError per group. Fields are null when valid.
 */
export function validateGroups(
  groups: EditableGroup[],
  config: PuzzleEditorConfig,
): GroupValidationError[] {
  // Collect all words across all groups for duplicate detection
  const allWords: { word: string; groupIdx: number; wordIdx: number }[] = [];
  groups.forEach((group, gi) => {
    group.words.forEach((word, wi) => {
      if (word.trim()) {
        allWords.push({ word: word.trim().toLowerCase(), groupIdx: gi, wordIdx: wi });
      }
    });
  });

  // Build a set of (groupIdx, wordIdx) pairs that are duplicates
  const seen = new Map<string, { groupIdx: number; wordIdx: number }>();
  const duplicatePositions = new Set<string>();
  for (const entry of allWords) {
    const key = entry.word;
    if (seen.has(key)) {
      const first = seen.get(key)!;
      duplicatePositions.add(`${first.groupIdx}-${first.wordIdx}`);
      duplicatePositions.add(`${entry.groupIdx}-${entry.wordIdx}`);
    } else {
      seen.set(key, { groupIdx: entry.groupIdx, wordIdx: entry.wordIdx });
    }
  }

  return groups.map((group, gi) => {
    const categoryName = group.category_name.trim()
      ? null
      : "Category name is required";

    const words: (string | null)[] = Array.from({ length: config.wordsPerGroup }, (_, wi) => {
      const word = (group.words[wi] ?? "").trim();
      if (!word) return "Word is required";
      if (duplicatePositions.has(`${gi}-${wi}`)) return "Duplicate word";
      return null;
    });

    return { categoryName, words };
  });
}

/**
 * Returns true only when every error in every group is null —
 * i.e. the puzzle is structurally valid and ready to save.
 */
export function isPuzzleValid(
  groups: EditableGroup[],
  config: PuzzleEditorConfig,
): boolean {
  if (groups.length !== config.groupCount) return false;
  const errors = validateGroups(groups, config);
  return errors.every(
    (e) => e.categoryName === null && e.words.every((w) => w === null),
  );
}

/** Returns a blank puzzle template for the given config. */
export function makeBlankGroups(config: PuzzleEditorConfig): EditableGroup[] {
  return Array.from({ length: config.groupCount }, () => ({
    category_name: "",
    words: Array.from({ length: config.wordsPerGroup }, () => ""),
  }));
}
