import React from "react";
import Navbar from "./components/navbar/Navbar";
import Game from "./components/Game";
import { SelectedWordsProvider } from "./context/SelectedWordsContext";

const App: React.FC = () => {
  return (
    <SelectedWordsProvider>
      <div className="app">
        <Navbar />
        <Game />
      </div>
    </SelectedWordsProvider>
  );
};

export default App;
