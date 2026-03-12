import React, { useState } from "react";
import Navbar from "../Navbar/Navbar";
import ConnectionsGame from "../ConnectionsGame/ConnectionsGame";
import LandingPage from "../LandingPage/LandingPage";
import ProfileScreen from "../ProfileScreen/ProfileScreen";
import AdminScreen from "../AdminScreen/AdminScreen";
import PuzzleEditor from "../AdminScreen/PuzzleEditor";
import { SelectedWordsProvider } from "../../context/SelectedWordsContext";
import { useAuth } from "../../context/AuthContext";
import { isAdminEmail } from "../../lib/adminUtils";
import { EditableGroup } from "../../types/admin";

// Top-level view — 'profile', 'admin', and 'editor' are only reachable when authenticated
type AppView = "game" | "profile" | "admin" | "editor";

const App: React.FC = () => {
  const { user, loading } = useAuth();
  // Track if user is playing as guest (not persisted)
  const [isGuestMode, setIsGuestMode] = useState(false);
  const [currentView, setCurrentView] = useState<AppView>("game");
  // When set, ConnectionsGame loads this specific game rather than calling /generate-grid.
  // Used for admin play-test mode.
  const [reviewGameId, setReviewGameId] = useState<string | null>(null);
  const [reviewPuzzleId, setReviewPuzzleId] = useState<string | null>(null);
  const [reviewTab, setReviewTab] = useState<"rejected" | "approved">("rejected");
  // Editor state — puzzleId=null means "new puzzle"
  const [editorPuzzleId, setEditorPuzzleId] = useState<string | null>(null);
  const [editorInitialGroups, setEditorInitialGroups] = useState<EditableGroup[] | undefined>(undefined);
  const [editorTimesServed, setEditorTimesServed] = useState<number>(0);

  const isAdmin = isAdminEmail(user?.email);

  // Handle playing as guest
  const handlePlayAsGuest = () => {
    setIsGuestMode(true);
  };

  // Called by AdminScreen when admin clicks "Play Test" on a puzzle card.
  const handlePlayTest = (gameId: string, puzzleId: string, tab: "rejected" | "approved") => {
    setReviewGameId(gameId);
    setReviewPuzzleId(puzzleId);
    setReviewTab(tab);
    setCurrentView("game");
  };

  // Called by ConnectionsGame when admin finishes a review game and clicks "Back to Admin".
  const handleBackFromReview = () => {
    setReviewGameId(null);
    setReviewPuzzleId(null);
    setCurrentView("admin");
  };

  // Called by AdminScreen or PuzzleReviewCard to open the editor.
  // No args = new puzzle; with args = edit existing.
  const handleOpenEditor = (
    puzzleId?: string,
    groups?: EditableGroup[],
    timesServed?: number,
  ) => {
    setEditorPuzzleId(puzzleId ?? null);
    setEditorInitialGroups(groups);
    setEditorTimesServed(timesServed ?? 0);
    setCurrentView("editor");
  };

  // Called by PuzzleEditor on successful save. Navigate back to admin.
  const handleEditorSave = (_savedPuzzleId: string) => {
    setCurrentView("admin");
  };

  // Show landing page if not authenticated and not in guest mode
  const showLandingPage = !user && !isGuestMode;

  // Show loading state while checking authentication
  if (loading) {
    return (
      <div id="app-container" className="app">
        <Navbar showLowerNav={false} />
        <div id="loading-container" className="loading-container">
          <p id="loading-text">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <SelectedWordsProvider>
      <div id="app-container" className="app">
        <Navbar
          showLowerNav={!showLandingPage}
          onNavigateToProfile={() => setCurrentView("profile")}
          onNavigateToAdmin={isAdmin ? () => setCurrentView("admin") : undefined}
        />
        {showLandingPage ? (
          <LandingPage onPlayAsGuest={handlePlayAsGuest} />
        ) : currentView === "profile" ? (
          <ProfileScreen onBack={() => setCurrentView("game")} />
        ) : currentView === "admin" ? (
          <AdminScreen
            onBack={() => setCurrentView("game")}
            onPlayTest={handlePlayTest}
            onOpenEditor={handleOpenEditor}
          />
        ) : currentView === "editor" ? (
          <PuzzleEditor
            puzzleId={editorPuzzleId ?? undefined}
            initialGroups={editorInitialGroups}
            timesServed={editorTimesServed}
            onSave={handleEditorSave}
            onCancel={() => setCurrentView("admin")}
          />
        ) : (
          <ConnectionsGame
            reviewGameId={reviewGameId}
            reviewPuzzleId={reviewPuzzleId ?? undefined}
            reviewTab={reviewTab}
            onReviewComplete={reviewGameId ? handleBackFromReview : undefined}
          />
        )}
      </div>
    </SelectedWordsProvider>
  );
};

export default App;
