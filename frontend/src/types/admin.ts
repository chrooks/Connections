/** A single group within a puzzle, as returned by the admin review endpoints. */
export interface AdminPuzzleGroup {
  relationship: string;
  words: string[];
}

/** A puzzle as returned by GET /admin/puzzles/rejected or /admin/puzzles/approved. */
export interface AdminPuzzle {
  puzzle_id: string;
  validation_score: number | null;
  auto_fail_reasons: string[];
  warnings: string[];
  created_at: string;
  /** Only present for approved puzzles. */
  approved_at?: string;
  /** Set when an admin has manually edited this puzzle's content. */
  edited_at?: string;
  /** How many times this puzzle has been served to players. */
  times_served: number;
  groups: AdminPuzzleGroup[];
}

/** Which tab is currently active in the AdminScreen. */
export type AdminTab = "rejected" | "approved";

/** A group being edited in the PuzzleEditor. Words are always fixed-length per config. */
export interface EditableGroup {
  category_name: string;
  words: string[];
}
