/**
 * AdminScreen — puzzle review and approval interface.
 *
 * Shows two tabs: Rejected (puzzles that failed auto-validation) and Approved
 * (puzzles currently in the serve pool). Admins can reveal answers, play-test
 * any puzzle, and approve/reject individual puzzles.
 *
 * Only reachable when the user's email is in VITE_ADMIN_EMAILS (checked in App.tsx).
 * All API calls are further guarded by the backend's require_admin decorator.
 */

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { toast } from "react-toastify";
import { adminApiGet } from "../../lib/adminApi";
import { AdminPuzzle, AdminTab, EditableGroup } from "../../types/admin";
import PuzzleReviewCard from "./PuzzleReviewCard";
import "./AdminScreen.scss";

type SortField = "created_at" | "validation_score" | "puzzle_id";
type SortDir = "asc" | "desc";

interface AdminScreenProps {
  onBack: () => void;
  onPlayTest: (gameId: string, puzzleId: string, tab: AdminTab) => void;
  onOpenEditor: (puzzleId?: string, groups?: EditableGroup[], timesServed?: number) => void;
}

const SORT_LABELS: Record<SortField, string> = {
  created_at: "Date",
  validation_score: "Score",
  puzzle_id: "ID",
};

function sortPuzzles(puzzles: AdminPuzzle[], field: SortField, dir: SortDir): AdminPuzzle[] {
  return [...puzzles].sort((a, b) => {
    let cmp = 0;
    if (field === "validation_score") {
      // Nulls sort last regardless of direction
      const aScore = a.validation_score ?? -Infinity;
      const bScore = b.validation_score ?? -Infinity;
      cmp = aScore - bScore;
    } else if (field === "created_at") {
      cmp = a.created_at.localeCompare(b.created_at);
    } else {
      cmp = a.puzzle_id.localeCompare(b.puzzle_id);
    }
    return dir === "asc" ? cmp : -cmp;
  });
}

const AdminScreen: React.FC<AdminScreenProps> = ({ onBack, onPlayTest, onOpenEditor }) => {
  const [activeTab, setActiveTab] = useState<AdminTab>("rejected");
  const [rejectedPuzzles, setRejectedPuzzles] = useState<AdminPuzzle[]>([]);
  const [approvedPuzzles, setApprovedPuzzles] = useState<AdminPuzzle[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [currentPage, setCurrentPage] = useState(1);

  const PAGE_SIZE = 15;

  const fetchPuzzles = useCallback(async (tab: AdminTab) => {
    setLoading(true);
    setError(null);
    try {
      const endpoint = tab === "rejected" ? "/puzzles/rejected" : "/puzzles/approved";
      const res = await adminApiGet(endpoint);
      const json = await res.json();
      if (!res.ok) throw new Error(json.message ?? "Failed to load puzzles");
      const puzzles: AdminPuzzle[] = json.data.puzzles;
      if (tab === "rejected") {
        setRejectedPuzzles(puzzles);
      } else {
        setApprovedPuzzles(puzzles);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load puzzles";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load the active tab's data on mount and whenever the tab changes.
  // Also reset to page 1 so the user doesn't land mid-list after switching tabs.
  useEffect(() => {
    fetchPuzzles(activeTab);
    setCurrentPage(1);
  }, [activeTab, fetchPuzzles]);

  // Remove a puzzle from local state after it is approved or rejected (optimistic update).
  const handleStatusChanged = (puzzleId: string) => {
    if (activeTab === "rejected") {
      setRejectedPuzzles(prev => prev.filter(p => p.puzzle_id !== puzzleId));
    } else {
      setApprovedPuzzles(prev => prev.filter(p => p.puzzle_id !== puzzleId));
    }
  };

  // Toggle direction if same field clicked; switch field + reset to desc otherwise.
  // Always jump back to page 1 so the user doesn't land on an empty page.
  const handleSortClick = (field: SortField) => {
    if (field === sortField) {
      setSortDir(prev => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
    setCurrentPage(1);
  };

  const rawPuzzles = activeTab === "rejected" ? rejectedPuzzles : approvedPuzzles;

  // Sorting is purely a derived view — the fetched arrays remain unsorted in state
  // so switching sort order never requires a network request.
  const activePuzzles = useMemo(
    () => sortPuzzles(rawPuzzles, sortField, sortDir),
    [rawPuzzles, sortField, sortDir],
  );

  const totalPages = Math.max(1, Math.ceil(activePuzzles.length / PAGE_SIZE));
  // Clamp currentPage in case puzzles are removed (approve/reject) and the last
  // page shrinks to zero items.
  const safePage = Math.min(currentPage, totalPages);
  const pagedPuzzles = activePuzzles.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const sortDirArrow = sortDir === "asc" ? "↑" : "↓";

  return (
    <div id="admin-screen" className="admin-screen">
      <div id="admin-header" className="admin-header">
        <button id="admin-back-button" className="admin-back-button" onClick={onBack}>
          ← Back to Game
        </button>
        <h1 id="admin-title" className="admin-title">Puzzle Review</h1>
        <button
          id="admin-new-puzzle-button"
          className="btn btn-primary admin-new-puzzle-button"
          onClick={() => onOpenEditor()}
        >
          + New Puzzle
        </button>
      </div>

      <div id="admin-tabs" className="admin-tabs">
        <button
          id="admin-tab-rejected"
          className={`admin-tab-button${activeTab === "rejected" ? " admin-tab-button--active" : ""}`}
          onClick={() => setActiveTab("rejected")}
        >
          Rejected ({rejectedPuzzles.length})
        </button>
        <button
          id="admin-tab-approved"
          className={`admin-tab-button${activeTab === "approved" ? " admin-tab-button--active" : ""}`}
          onClick={() => setActiveTab("approved")}
        >
          Approved ({approvedPuzzles.length})
        </button>
      </div>

      {/* Sort controls — only shown when there's something to sort */}
      {!loading && !error && rawPuzzles.length > 0 && (
        <div id="admin-sort-controls" className="admin-sort-controls">
          <span className="admin-sort-label">Sort:</span>
          {(Object.keys(SORT_LABELS) as SortField[]).map(field => (
            <button
              key={field}
              id={`admin-sort-${field}`}
              className={`admin-sort-button${sortField === field ? " admin-sort-button--active" : ""}`}
              onClick={() => handleSortClick(field)}
            >
              {SORT_LABELS[field]}
              {sortField === field && (
                <span className="admin-sort-arrow">{sortDirArrow}</span>
              )}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div id="admin-loading" className="admin-puzzle-list">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="puzzle-skeleton-card">
              <div className="puzzle-skeleton-header">
                <div className="puzzle-skeleton-block puzzle-skeleton-block--badge" />
                <div className="puzzle-skeleton-block puzzle-skeleton-block--id" />
                <div className="puzzle-skeleton-block puzzle-skeleton-block--date" />
              </div>
              <div className="puzzle-skeleton-grid">
                {Array.from({ length: 16 }).map((_, j) => (
                  <div key={j} className="puzzle-skeleton-block puzzle-skeleton-block--word" />
                ))}
              </div>
              <div className="puzzle-skeleton-actions">
                {Array.from({ length: 4 }).map((_, j) => (
                  <div key={j} className="puzzle-skeleton-block puzzle-skeleton-block--btn" />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {error && !loading && (
        <p id="admin-error" className="admin-error">{error}</p>
      )}

      {!loading && !error && activePuzzles.length === 0 && (
        <p id="admin-empty" className="admin-empty">
          No {activeTab} puzzles found.
        </p>
      )}

      <div id="admin-puzzle-list" className="admin-puzzle-list">
        {pagedPuzzles.map(puzzle => (
          <PuzzleReviewCard
            key={puzzle.puzzle_id}
            puzzle={puzzle}
            tab={activeTab}
            onPlayTest={onPlayTest}
            onStatusChanged={handleStatusChanged}
            onEdit={(puzzleId, groups) => onOpenEditor(puzzleId, groups, puzzle.times_served)}
          />
        ))}
      </div>

      {totalPages > 1 && (
        <div id="admin-pagination" className="admin-pagination">
          <button
            id="admin-pagination-prev"
            className="admin-pagination-btn"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={safePage === 1}
          >
            ← Prev
          </button>
          <span id="admin-pagination-info" className="admin-pagination-info">
            Page {safePage} of {totalPages}
          </span>
          <button
            id="admin-pagination-next"
            className="admin-pagination-btn"
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={safePage === totalPages}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
};

export default AdminScreen;
