import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Folder,
  CalendarDays,
  Settings,
  Zap,
  History,
  Layout as LayoutIcon,
} from "lucide-react";

import ErrorBoundary from "./ErrorBoundary";

export const Layout: React.FC = () => {
  const navItems = [
    { to: "/", icon: Folder, label: "Хранилище" },
    { to: "/editor", icon: Settings, label: "Редактор пар" },
    { to: "/calendar", icon: CalendarDays, label: "Календарь" },
    { to: "/generation", icon: Zap, label: "Генерация" },
    { to: "/history", icon: History, label: "История" },
    { to: "/schedule", icon: LayoutIcon, label: "Редактор" },
  ];

  return (
    <div className="min-h-screen">
      {/* Header with Navigation Pills */}
      <header
        style={{
          position: "sticky",
          top: 0,
          backgroundColor: "rgba(244, 245, 248, 0.8)",
          backdropFilter: "blur(10px)",
          zIndex: 100,
          padding: "1.5rem 2.5rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          maxWidth: "1200px",
          margin: "0 auto",
        }}
      >
        <div className="flex items-center gap-4">
          <div
            style={{
              background: "var(--brand)",
              color: "white",
              width: "40px",
              height: "40px",
              borderRadius: "12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 900,
              fontSize: "1.25rem",
            }}
          >
            S
          </div>
          <div>
            <h1
              style={{
                fontSize: "1.125rem",
                fontWeight: 800,
                color: "var(--text-primary)",
              }}
            >
              Scheduler
            </h1>
            <p
              style={{
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
                fontWeight: 600,
              }}
            >
              University MVP
            </p>
          </div>
        </div>

        <nav className="pills-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `pill ${isActive ? "active" : ""}`}
            >
              <div
                style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
              >
                <item.icon size={18} />
                <span>{item.label}</span>
              </div>
            </NavLink>
          ))}
        </nav>

        <button
          style={{
            padding: "0.75rem",
            borderRadius: "12px",
            backgroundColor: "white",
            border: "1px solid var(--border-light)",
            color: "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "var(--shadow-subtle)",
          }}
        >
          <Settings size={20} />
        </button>
      </header>

      {/* Main Content */}
      <main className="p-10">
        <div className="max-w-6xl animate-fade-in">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
};
