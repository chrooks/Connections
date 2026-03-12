/**
 * PuzzleReviewCard — a single puzzle entry in the admin review list.
 *
 * Shows the 16 words in a flat grid by default. The admin can:
 *   - Toggle "Reveal Answers" to see color-coded category rows with names
 *   - Click "Play Test" to launch a full play-test game session
 *   - Click "✏ Edit" to open the puzzle editor pre-filled with this puzzle
 *   - Click "Approve" (rejected tab) or "Reject" (approved tab) to change status
 */

import React, { useState } from "react";
import { toast } from "react-toastify";
import { adminApiPost } from "../../lib/adminApi";
import { AdminPuzzle, AdminTab, EditableGroup } from "../../types/admin";

// NYT-style difficulty colors: index 0=yellow (easiest) … 3=purple (hardest)
const DIFFICULTY_COLORS = ["#f9df6d", "#a0c35a", "#b0c4ef", "#ba81c5"];

interface PuzzleReviewCardProps {
  puzzle: AdminPuzzle;
  tab: AdminTab;
  onPlayTest: (gameId: string, puzzleId: string, tab: AdminTab) => void;
  onStatusChanged: (puzzleId: string) => void;
  onEdit: (puzzleId: string, groups: EditableGroup[]) => void;
}

// Truncates a UUID to 8 characters for compact display
function shortId(id: string): string {
  return id.slice(0, 8);
}

// Formats an ISO date string to e.g. "Mar 11 2026"
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const PuzzleReviewCard: React.FC<PuzzleReviewCardProps> = ({
  puzzle,
  tab,
  onPlayTest,
  onStatusChanged,
  onEdit,
}) => {
  const [showAnswers, setShowAnswers] = useState(false);
  const [showWarnings, setShowWarnings] = useState(false);
  const [isStartingGame, setIsStartingGame] = useState(false);
  const [isActioning, setIsActioning] = useState(false);

  // Score badge color: red below 0.5, yellow 0.5–0.7, green above
  const scoreColor = (() => {
    if (puzzle.validation_score === null) return "#aaa";
    if (puzzle.validation_score < 0.5) return "#e74c3c";
    if (puzzle.validation_score < 0.7) return "#f39c12";
    return "#27ae60";
  })();

  const handlePlayTest = async () => {
    setIsStartingGame(true);
    try {
      const res = await adminApiPost(`/puzzles/${puzzle.puzzle_id}/start-review-game`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.message ?? "Failed to start review game");
      onPlayTest(json.data.game_id, puzzle.puzzle_id, tab);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start play test");
    } finally {
      setIsStartingGame(false);
    }
  };

  const handleAction = async () => {
    setIsActioning(true);
    const endpoint =
      tab === "rejected"
        ? `/puzzles/${puzzle.puzzle_id}/approve`
        : `/puzzles/${puzzle.puzzle_id}/reject`;
    try {
      const res = await adminApiPost(endpoint);
      if (!res.ok) {
        const json = await res.json();
        throw new Error(json.message ?? "Action failed");
      }
      const label = tab === "rejected" ? "approved" : "rejected";
      toast.success(`Puzzle ${label}`);
      onStatusChanged(puzzle.puzzle_id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed");
    } finally {
      setIsActioning(false);
    }
  };

  const handleEdit = () => {
    // Convert the puzzle's AdminPuzzleGroups to EditableGroups for the editor
    const editableGroups: EditableGroup[] = puzzle.groups.map(g => ({
      category_name: g.relationship,
      words: g.words,
    }));
    onEdit(puzzle.puzzle_id, editableGroups);
  };

  // All 16 words flat, in group order (difficulty 0→3)
  const allWords = puzzle.groups.flatMap(g => g.words);

  return (
    <div
      id={`puzzle-card-${puzzle.puzzle_id}`}
      className="puzzle-review-card"
    >
      {/* Card header: score badge, short ID, creation date, edited badge */}
      <div id={`puzzle-card-header-${puzzle.puzzle_id}`} className="puzzle-review-card-header">
        <span
          id={`puzzle-score-badge-${puzzle.puzzle_id}`}
          className="puzzle-review-score-badge"
          style={{ backgroundColor: scoreColor }}
        >
          {puzzle.validation_score !== null
            ? puzzle.validation_score.toFixed(2)
            : "N/A"}
        </span>
        <span id={`puzzle-id-${puzzle.puzzle_id}`} className="puzzle-review-id">
          #{shortId(puzzle.puzzle_id)}
        </span>
        <span id={`puzzle-date-${puzzle.puzzle_id}`} className="puzzle-review-date">
          {formatDate(puzzle.approved_at ?? puzzle.created_at)}
        </span>
        {puzzle.edited_at && (
          <span
            id={`puzzle-edited-badge-${puzzle.puzzle_id}`}
            className="puzzle-edited-badge"
            title={`Edited ${formatDate(puzzle.edited_at)}`}
          >
            ✏ Edited
          </span>
        )}
      </div>

      {/* Collapsible validation issues — collapsed by default to keep the card compact */}
      {(puzzle.auto_fail_reasons.length > 0 || puzzle.warnings.length > 0) && (
        <div id={`puzzle-warnings-section-${puzzle.puzzle_id}`} className="puzzle-review-warnings-section">
          <button
            id={`puzzle-warnings-toggle-${puzzle.puzzle_id}`}
            className="puzzle-review-warnings-toggle"
            onClick={() => setShowWarnings(prev => !prev)}
          >
            {showWarnings ? "▾" : "▸"}{" "}
            {puzzle.auto_fail_reasons.length > 0
              ? `${puzzle.auto_fail_reasons.length} fail reason${puzzle.auto_fail_reasons.length > 1 ? "s" : ""}`
              : ""
            }
            {puzzle.auto_fail_reasons.length > 0 && puzzle.warnings.length > 0 ? ", " : ""}
            {puzzle.warnings.length > 0
              ? `${puzzle.warnings.length} warning${puzzle.warnings.length > 1 ? "s" : ""}`
              : ""
            }
          </button>
          {showWarnings && (
            <>
              {puzzle.auto_fail_reasons.length > 0 && (
                <div id={`puzzle-fail-reasons-${puzzle.puzzle_id}`} className="puzzle-review-tags">
                  {puzzle.auto_fail_reasons.map((reason, i) => (
                    <span
                      key={i}
                      id={`puzzle-fail-tag-${puzzle.puzzle_id}-${i}`}
                      className="puzzle-review-fail-tag"
                    >
                      {reason}
                    </span>
                  ))}
                </div>
              )}
              {puzzle.warnings.length > 0 && (
                <div id={`puzzle-warnings-${puzzle.puzzle_id}`} className="puzzle-review-tags">
                  {puzzle.warnings.map((warning, i) => (
                    <span
                      key={i}
                      id={`puzzle-warning-tag-${puzzle.puzzle_id}-${i}`}
                      className="puzzle-review-warning-tag"
                    >
                      {warning}
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Word display: flat grid or revealed category rows */}
      {showAnswers ? (
        <div id={`puzzle-groups-${puzzle.puzzle_id}`} className="puzzle-review-groups">
          {puzzle.groups.map((group, i) => (
            <div
              key={group.relationship}
              id={`puzzle-group-${puzzle.puzzle_id}-${i}`}
              className="puzzle-review-group"
              style={{ backgroundColor: DIFFICULTY_COLORS[i] }}
            >
              <span className="puzzle-review-group-name">{group.relationship}</span>
              <span className="puzzle-review-group-words">
                {group.words.join(", ")}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div id={`puzzle-grid-${puzzle.puzzle_id}`} className="puzzle-review-grid">
          {allWords.map(word => (
            <span key={word} className="puzzle-review-word">{word}</span>
          ))}
        </div>
      )}

      {/* Action buttons */}
      <div id={`puzzle-actions-${puzzle.puzzle_id}`} className="puzzle-review-actions">
        <button
          id={`puzzle-reveal-button-${puzzle.puzzle_id}`}
          className="puzzle-review-btn puzzle-review-btn--secondary"
          onClick={() => setShowAnswers(prev => !prev)}
        >
          {showAnswers ? "Hide Answers" : "Reveal Answers"}
        </button>
        <button
          id={`puzzle-play-button-${puzzle.puzzle_id}`}
          className="puzzle-review-btn puzzle-review-btn--secondary"
          onClick={handlePlayTest}
          disabled={isStartingGame}
        >
          {isStartingGame ? "Starting..." : "▶ Play Test"}
        </button>
        <button
          id={`puzzle-edit-button-${puzzle.puzzle_id}`}
          className="puzzle-review-btn puzzle-review-btn--edit"
          onClick={handleEdit}
        >
          ✏ Edit
        </button>
        <button
          id={`puzzle-action-button-${puzzle.puzzle_id}`}
          className={`puzzle-review-btn ${tab === "rejected" ? "puzzle-review-btn--approve" : "puzzle-review-btn--reject"}`}
          onClick={handleAction}
          disabled={isActioning}
        >
          {isActioning
            ? "..."
            : tab === "rejected"
            ? "✓ Approve"
            : "✗ Reject"}
        </button>
      </div>
    </div>
  );
};

export default PuzzleReviewCard;
