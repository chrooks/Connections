export interface UserStats {
  wins: number;
  losses: number;
  forfeits: number;
  avgCompletionTimeSeconds: number | null;
}

// Shape of a single connection group as stored in game_sessions
export interface HistoryConnection {
  relationship: string;
  words: string[];
  guessed: boolean;
}

export interface GameHistoryEntry {
  gameId: string;
  puzzleNumber: number | null;
  outcome: 'WIN' | 'LOSS' | 'FORFEIT';
  completionTimeSeconds: number | null;
  playedAt: string;
  connections: HistoryConnection[];
  previousGuesses: string[][];
  /** True when the source puzzle was edited by an admin after this session was played. */
  puzzleModifiedSincePlayed?: boolean;
}
