/**
 * User menu component shown in the navbar when authenticated.
 *
 * Displays a user icon that opens a dropdown with email (clickable to profile) and sign out.
 */

import React, { useState, useRef, useEffect } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faUser } from "@fortawesome/free-solid-svg-icons";
import { useAuth } from "../../context/AuthContext";
import "./Auth.scss";

interface UserMenuProps {
  onNavigateToProfile?: () => void;
  onNavigateToAdmin?: () => void;
}

const UserMenu: React.FC<UserMenuProps> = ({ onNavigateToProfile, onNavigateToAdmin }) => {
  const { user, signOut } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!user) return null;

  return (
    <div id="user-menu" className="user-menu" ref={menuRef}>
      <button
        id="user-menu-button"
        className="user-menu-icon"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="User menu"
      >
        <FontAwesomeIcon icon={faUser} />
      </button>

      {isOpen && (
        <div id="user-menu-dropdown" className="user-menu-dropdown">
          {/* Email is the profile link */}
          <button
            id="user-menu-profile-link"
            className="user-menu-profile-link"
            onClick={() => {
              onNavigateToProfile?.();
              setIsOpen(false);
            }}
          >
            {user.email}
          </button>
          {/* Admin link — only rendered when the parent passes the callback (admin users only) */}
          {onNavigateToAdmin && (
            <button
              id="user-menu-admin-link"
              className="user-menu-admin-link"
              onClick={() => {
                onNavigateToAdmin();
                setIsOpen(false);
              }}
            >
              Admin
            </button>
          )}
          <button
            id="sign-out-button"
            onClick={() => {
              signOut();
              setIsOpen(false);
            }}
            className="user-menu-logout"
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
};

export default UserMenu;
