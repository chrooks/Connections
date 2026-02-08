import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './components/App/App'
import { AuthProvider } from './context/AuthContext'
import 'bootstrap/dist/css/bootstrap.min.css';
import "../styles/main.scss";

// Wrap App with AuthProvider to make auth state available throughout the app
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
)
