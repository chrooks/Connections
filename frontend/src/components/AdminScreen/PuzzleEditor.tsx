import { useState, useCallback } from "react";
import { toast } from "react-toastify";
import { EditableGroup } from "../../types/admin";
import {
  PuzzleEditorConfig,
  CLASSIC_CONFIG,
  GroupValidationError,
  validateGroups,
  isPuzzleValid,
  makeBlankGroups,
} from "../../lib/puzzleEditorUtils";
import { adminApiPatch, adminApiPost } from "../../lib/adminApi";

interface PuzzleEditorProps {
  /** If provided, editing an existing puzzle. Absent = creating a new one. */
  puzzleId?: string;
  /** Pre-filled groups when editing; blank template when creating. */
  initialGroups?: EditableGroup[];
  /** How many groups and words per group. Defaults to CLASSIC_CONFIG. */
  config?: PuzzleEditorConfig;
  /** How many times this puzzle has been served (shown in warning banner). */
  timesServed?: number;
  onSave: (puzzleId: string) => void;
  onCancel: () => void;
}

export default function PuzzleEditor({
  puzzleId,
  initialGroups,
  config = CLASSIC_CONFIG,
  timesServed = 0,
  onSave,
  onCancel,
}: PuzzleEditorProps) {
  const [groups, setGroups] = useState<EditableGroup[]>(
    () => initialGroups ?? makeBlankGroups(config),
  );
  const [isSaving, setIsSaving] = useState(false);
  // Only show validation errors after the first save attempt
  const [showErrors, setShowErrors] = useState(false);

  const errors: GroupValidationError[] = showErrors
    ? validateGroups(groups, config)
    : groups.map(() => ({
        categoryName: null,
        words: Array(config.wordsPerGroup).fill(null),
      }));

  const valid = isPuzzleValid(groups, config);

  // Swap two adjacent groups (for reordering difficulty rank)
  const swapGroups = useCallback((indexA: number, indexB: number) => {
    setGroups((prev) => {
      const next = [...prev];
      [next[indexA], next[indexB]] = [next[indexB], next[indexA]];
      return next;
    });
  }, []);

  const updateCategoryName = useCallback((gi: number, value: string) => {
    setGroups((prev) => {
      const next = [...prev];
      next[gi] = { ...next[gi], category_name: value };
      return next;
    });
  }, []);

  const updateWord = useCallback((gi: number, wi: number, value: string) => {
    setGroups((prev) => {
      const next = [...prev];
      const words = [...next[gi].words];
      words[wi] = value;
      next[gi] = { ...next[gi], words };
      return next;
    });
  }, []);

  const handleSave = async () => {
    setShowErrors(true);
    if (!valid) return;

    setIsSaving(true);
    try {
      const payload = { groups: groups.map((g) => ({ category_name: g.category_name, words: g.words })) };

      if (puzzleId) {
        const res = await adminApiPatch(`/puzzles/${puzzleId}`, payload);
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.message ?? "Failed to save puzzle");
        }
        toast.success("Puzzle saved");
        onSave(puzzleId);
      } else {
        const res = await adminApiPost("/puzzles", { ...payload, config_name: "classic" });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.message ?? "Failed to create puzzle");
        }
        const body = await res.json();
        toast.success("Puzzle created and approved");
        onSave(body.data.puzzle_id);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div id="puzzle-editor" className="puzzle-editor">
      {/* Header row */}
      <div className="puzzle-editor-header">
        <button
          id="puzzle-editor-cancel-button"
          className="btn btn-outline-secondary puzzle-editor-cancel-btn"
          onClick={onCancel}
          disabled={isSaving}
        >
          ← Cancel
        </button>
        <h2 className="puzzle-editor-title">
          {puzzleId ? "Edit Puzzle" : "New Puzzle"}
        </h2>
        <button
          id="puzzle-editor-save-button"
          className="btn btn-success puzzle-editor-save-btn"
          onClick={handleSave}
          disabled={isSaving || (showErrors && !valid)}
        >
          {isSaving ? "Saving…" : "Save ✓"}
        </button>
      </div>

      {/* Served-count warning banner */}
      {timesServed > 0 && (
        <div id="puzzle-editor-served-banner" className="alert alert-info puzzle-editor-banner">
          This puzzle has been played <strong>{timesServed}</strong> time
          {timesServed !== 1 ? "s" : ""} — edits won't affect existing sessions.
        </div>
      )}

      {/* Group rows */}
      {groups.map((group, gi) => {
        const groupErrors = errors[gi];
        return (
          <div
            key={gi}
            id={`puzzle-editor-group-${gi}`}
            className="puzzle-editor-group"
          >
            {/* Up/down reorder buttons */}
            <div className="puzzle-editor-group-order-buttons">
              <button
                id={`puzzle-editor-group-up-${gi}`}
                className="btn btn-sm btn-outline-secondary"
                onClick={() => swapGroups(gi - 1, gi)}
                disabled={gi === 0}
                title="Move up (easier)"
              >
                ▲
              </button>
              <button
                id={`puzzle-editor-group-down-${gi}`}
                className="btn btn-sm btn-outline-secondary"
                onClick={() => swapGroups(gi, gi + 1)}
                disabled={gi === groups.length - 1}
                title="Move down (harder)"
              >
                ▼
              </button>
            </div>

            {/* Category name + word fields */}
            <div className="puzzle-editor-group-fields">
              <div className="puzzle-editor-category-row">
                <label
                  htmlFor={`puzzle-editor-category-${gi}`}
                  className="puzzle-editor-label"
                >
                  Category {gi + 1}
                </label>
                <input
                  id={`puzzle-editor-category-${gi}`}
                  type="text"
                  className={`puzzle-editor-category-input${groupErrors.categoryName ? " puzzle-editor-input--error" : ""}`}
                  value={group.category_name}
                  onChange={(e) => updateCategoryName(gi, e.target.value)}
                  placeholder="Category name…"
                />
                {groupErrors.categoryName && (
                  <span className="puzzle-editor-error-msg">
                    {groupErrors.categoryName}
                  </span>
                )}
              </div>

              <div className="puzzle-editor-words-grid">
                {Array.from({ length: config.wordsPerGroup }, (_, wi) => (
                  <div key={wi} className="puzzle-editor-word-cell">
                    <input
                      id={`puzzle-editor-word-${gi}-${wi}`}
                      type="text"
                      className={`puzzle-editor-word-input${groupErrors.words[wi] ? " puzzle-editor-input--error" : ""}`}
                      value={group.words[wi] ?? ""}
                      onChange={(e) => updateWord(gi, wi, e.target.value)}
                      placeholder={`Word ${wi + 1}`}
                    />
                    {groupErrors.words[wi] && (
                      <span className="puzzle-editor-error-msg">
                        {groupErrors.words[wi]}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
