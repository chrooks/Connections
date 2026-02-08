/**
 * Authentication modal for login and signup.
 *
 * Provides forms for email/password sign in and sign up with
 * error handling and loading states.
 */

import React, { useState } from "react";
import Modal from "react-modal";
import { useAuth } from "../../context/AuthContext";
import "./Auth.scss";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// Set app element for accessibility (required by react-modal)
Modal.setAppElement("#root");

const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { signIn, signUp } = useAuth();

  // Form state
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // Handle form submission for email/password auth
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);

    // Validate passwords match for sign up
    if (isSignUp && password !== confirmPassword) {
      setError("Passwords do not match");
      setLoading(false);
      return;
    }

    // Validate password length
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      setLoading(false);
      return;
    }

    try {
      if (isSignUp) {
        const { error } = await signUp(email, password);
        if (error) {
          setError(error.message);
        } else {
          setMessage("Check your email to confirm your account!");
        }
      } else {
        const { error } = await signIn(email, password);
        if (error) {
          setError(error.message);
        } else {
          // Reset form and close modal on successful sign in
          resetForm();
          onClose();
        }
      }
    } catch {
      setError("An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  };

  // Reset form state
  const resetForm = () => {
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    setError(null);
    setMessage(null);
  };

  // Toggle between sign in and sign up modes
  const toggleMode = () => {
    setIsSignUp(!isSignUp);
    setError(null);
    setMessage(null);
    setConfirmPassword("");
  };

  // Handle modal close - reset form state
  const handleClose = () => {
    resetForm();
    setIsSignUp(false);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onRequestClose={handleClose}
      className="auth-modal"
      overlayClassName="auth-modal-overlay"
    >
      <div id="auth-modal-content" className="auth-modal-content">
        <button id="auth-modal-close-button" onClick={handleClose} className="auth-close-btn" aria-label="Close">
          &times;
        </button>

        <h2 id="auth-modal-title">{isSignUp ? "Create Account" : "Sign In"}</h2>

        {/* Error message display */}
        {error && <div id="auth-error-message" className="auth-error">{error}</div>}

        {/* Success message display */}
        {message && <div id="auth-success-message" className="auth-message">{message}</div>}

        {/* Email/Password form */}
        <form id="auth-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
              placeholder="you@example.com"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              minLength={6}
              placeholder="At least 6 characters"
            />
          </div>

          {/* Confirm password field (sign up only) */}
          {isSignUp && (
            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={loading}
                placeholder="Confirm your password"
              />
            </div>
          )}

          <button id="auth-submit-button" type="submit" disabled={loading} className="auth-submit-btn">
            {loading ? "Loading..." : isSignUp ? "Sign Up" : "Sign In"}
          </button>
        </form>

        {/* Toggle between sign in and sign up */}
        <p id="auth-toggle-text" className="auth-toggle">
          {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
          <button id="auth-toggle-mode-button" type="button" onClick={toggleMode} className="auth-toggle-btn">
            {isSignUp ? "Sign In" : "Sign Up"}
          </button>
        </p>
      </div>
    </Modal>
  );
};

export default AuthModal;
