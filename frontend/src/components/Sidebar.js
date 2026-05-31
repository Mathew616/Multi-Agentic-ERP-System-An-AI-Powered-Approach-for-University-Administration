// src/components/Sidebar.js
import React, { useContext } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { Home, Upload, ClipboardCheck, FileText, BarChart3 } from "lucide-react";
import dsuLogo from "../assets/dsu_logo.png";

const Sidebar = () => {
  const { user } = useContext(AuthContext);
  const location = useLocation();
  const navigate = useNavigate();

  if (!user) return null;

  const handleTrackerClick = () => {
    if (!user) return navigate("/");
    if (user.role === "iqc") navigate("/tracker");
    else if (user.role === "teacher") navigate("/teacher/tracker");
    else if (user.role === "student") navigate("/student/tracker");
  };

  const linksByRole = {
    student: [
      { path: "/upload", name: "Upload", icon: <Upload size={18} /> },
      { name: "Tracker", icon: <BarChart3 size={18} />, onClick: handleTrackerClick },
    ],
    teacher: [
      { path: "/upload", name: "Upload", icon: <Upload size={18} /> },
      { path: "/validate", name: "Validate", icon: <ClipboardCheck size={18} /> },
      { name: "Tracker", icon: <BarChart3 size={18} />, onClick: handleTrackerClick },
    ],
    iqc: [
      { path: "/validate", name: "Validate", icon: <ClipboardCheck size={18} /> },
      { path: "/admin", name: "Admin", icon: <FileText size={18} /> },
      { name: "Tracker", icon: <BarChart3 size={18} />, onClick: handleTrackerClick },
    ],
  };

  const links = linksByRole[user.role] || [];

  return (
    <aside className="w-64 bg-gray-900 text-white flex flex-col shadow-xl">
      <div className="flex items-center gap-3 p-6 border-b border-gray-800">
        <img
          src={dsuLogo}
          alt="DSU Logo"
          className="w-12 h-12 object-contain"
        />
        <div>
          <h2 className="text-lg font-semibold">DSU Portal</h2>
          <p className="text-xs text-gray-400">Event Management</p>
        </div>
      </div>

      <nav className="flex flex-col p-4 space-y-2">
        {links.map((link) =>
          link.path ? (
            <Link
              key={link.name}
              to={link.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-150 ${
                location.pathname === link.path
                  ? "bg-indigo-600 text-white shadow-md"
                  : "hover:bg-gray-800 text-gray-300 hover:text-white"
              }`}
            >
              {link.icon}
              <span className="font-medium">{link.name}</span>
            </Link>
          ) : (
            <button
              key={link.name}
              onClick={link.onClick}
              className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-gray-800 text-gray-300 hover:text-white transition-all duration-150 text-left"
            >
              {link.icon}
              <span className="font-medium">{link.name}</span>
            </button>
          )
        )}
      </nav>
    </aside>
  );
};

export default Sidebar;
