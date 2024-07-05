import React from "react";
import Navbar from "../Navbar/Navbar";
import ConnectionsGame from "../ConnectionsGame/ConnectionsGame";
import { SelectedWordsProvider } from "../../context/SelectedWordsContext";

const App: React.FC = () => {
  return (
    <SelectedWordsProvider>
      <div className="app">
        <Navbar />
        <ConnectionsGame />
      </div>
    </SelectedWordsProvider>
  );
};

export default App;
