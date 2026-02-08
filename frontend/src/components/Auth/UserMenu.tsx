/**
 * User menu component shown in the navbar when authenticated.
 *
 * Displays a user icon that opens a dropdown with email and sign out option.
 */

import React, { useState, useRef, useEffect } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faUser } from "@fortawesome/free-solid-svg-icons";
import { useAuth } from "../../context/AuthContext";
import "./Auth.scss";

const UserMenu: React.FC = () => {
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
    <div className="user-menu" ref={menuRef}>
      <button
        className="user-menu-icon"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="User menu"
      >
        <FontAwesomeIcon icon={faUser} />
      </button>

      {isOpen && (
        <div className="user-menu-dropdown">
          <div className="user-menu-email">{user.email}</div>
          <button
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
