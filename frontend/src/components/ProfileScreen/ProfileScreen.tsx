/**
 * ProfileScreen displays an authenticated user's play history and aggregate stats.
 *
 * Fetches two endpoints in parallel on mount:
 *   GET /user/stats   → wins, losses, forfeits, avg completion time
 *   GET /user/history → completed game sessions newest-first
 *
 * Only reachable when authenticated (App.tsx only renders this for logged-in users).
 */

import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { apiGet } from "../../lib/api";
import { UserStats, GameHistoryEntry } from "../../types/profile";
import GameHistoryModal from "./GameHistoryModal";
import "./ProfileScreen.scss";

interface ProfileScreenProps {
  onBack: () => void;
}

// Converts raw seconds to MM:SS display format
function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

const ProfileScreen: React.FC<ProfileScreenProps> = ({ onBack }) => {
  const { user } = useAuth();
  const [stats, setStats] = useState<UserStats | null>(null);
  const [history, setHistory] = useState<GameHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Clicking a history row sets this to open the detail modal
  const [selectedEntry, setSelectedEntry] = useState<GameHistoryEntry | null>(null);

  // Derive display name from email prefix (e.g. "chrooks" from "chrooks@example.com")
  const username = user?.email?.split("@")[0] ?? "Player";

  useEffect(() => {
    const fetchProfileData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch stats and history in parallel — they are independent queries
        const [statsRes, historyRes] = await Promise.all([
          apiGet("/user/stats"),
          apiGet("/user/history"),
        ]);

        if (!statsRes.ok || !historyRes.ok) {
          throw new Error("Failed to load profile data.");
        }

        const statsJson = await statsRes.json();
        const historyJson = await historyRes.json();

        setStats(statsJson.data);
        setHistory(historyJson.data.history);
      } catch (err) {
        console.error("ProfileScreen fetch error:", err);
        setError("Failed to load profile data. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchProfileData();
  }, []);

  return (
    <div id="profile-screen" className="profile-screen">
      {/* Header with back button and username */}
      <div id="profile-header" className="profile-header">
        <button
          id="profile-back-button"
          className="profile-back-button"
          onClick={onBack}
          aria-label="Back to game"
        >
          ← Back to Game
        </button>
      </div>

      {loading && (
        <div id="profile-loading" className="profile-loading">
          <p>Loading...</p>
        </div>
      )}

      {error && !loading && (
        <div id="profile-error" className="profile-error">
          <p>{error}</p>
          <button
            id="profile-retry-button"
            className="profile-retry-button"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && stats && (
        <>
          {/* Aggregate stats grid */}
          <div id="profile-stats-grid" className="profile-stats-grid">
            <div id="profile-stat-wins" className="profile-stat-card">
              <span className="profile-stat-value">{stats.wins}</span>
              <span className="profile-stat-label">Wins</span>
            </div>
            <div id="profile-stat-losses" className="profile-stat-card">
              <span className="profile-stat-value">{stats.losses}</span>
              <span className="profile-stat-label">Losses</span>
            </div>
            <div id="profile-stat-forfeits" className="profile-stat-card">
              <span className="profile-stat-value">{stats.forfeits}</span>
              <span className="profile-stat-label">Forfeits</span>
            </div>
            <div id="profile-stat-avg-time" className="profile-stat-card">
              <span className="profile-stat-value">
                {stats.avgCompletionTimeSeconds !== null
                  ? formatTime(stats.avgCompletionTimeSeconds)
                  : "--"}
              </span>
              <span className="profile-stat-label">Avg Time</span>
            </div>
          </div>

          {/* Game history section */}
          <div id="profile-history-section" className="profile-history-section">
            <h2 id="profile-history-heading" className="profile-history-heading">
              Game History
            </h2>

            {history.length === 0 ? (
              <p id="profile-no-games" className="profile-no-games">
                No completed games yet. Start playing!
              </p>
            ) : (
              <>
                {/* Column headers */}
                <div
                  id="profile-history-header"
                  className="profile-history-row profile-history-row--header"
                >
                  <span>Puzzle</span>
                  <span>Result</span>
                  <span>Time</span>
                  <span>Date</span>
                </div>

                <div id="profile-history-list" className="profile-history-list">
                  {history.map((entry, i) => (
                    // Each row is a button so it is keyboard-accessible and semantically correct
                    <button
                      key={i}
                      id={`profile-history-entry-${i}`}
                      className="profile-history-row profile-history-row--clickable"
                      onClick={() => setSelectedEntry(entry)}
                      aria-label={`View details for puzzle ${entry.puzzleNumber ?? "practice"}`}
                    >
                      <span className="profile-history-puzzle">
                        {entry.puzzleNumber !== null
                          ? `#${entry.puzzleNumber}`
                          : "Practice"}
                      </span>

                      <span
                        className={`profile-history-outcome profile-outcome-${entry.outcome.toLowerCase()}`}
                      >
                        {entry.outcome}
                      </span>

                      <span className="profile-history-time">
                        {entry.completionTimeSeconds !== null
                          ? formatTime(entry.completionTimeSeconds)
                          : "--"}
                      </span>

                      <span className="profile-history-date">
                        {new Date(entry.playedAt).toLocaleDateString()}
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </>
      )}

      {/* Detail modal — shown when a history row is clicked */}
      <GameHistoryModal
        entry={selectedEntry}
        onClose={() => setSelectedEntry(null)}
      />
    </div>
  );
};

export default ProfileScreen;
