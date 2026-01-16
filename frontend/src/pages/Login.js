// src/pages/Login.js
import React, { useState, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import dsuLogo from "../assets/dsu_logo.png"; // DSU logo
import dsuBg from "../assets/dsu.png"; // 🏫 Background image

const Login = () => {
  const { login } = useContext(AuthContext);
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post("/api/auth/login", { username, password });
      const { token, user } = res.data;
      login(token, user);

      // Redirect based on role
      setTimeout(() => {
        if (user.role === "student") navigate("/student/tracker");
        else if (user.role === "teacher") navigate("/teacher/tracker");
        else if (user.role === "iqc") navigate("/tracker");
      }, 300);
    } catch (err) {
      setError("Invalid username or password");
    }
  };

  return (
    <div
      className="flex items-center justify-center min-h-screen bg-cover bg-center"
      style={{
        backgroundImage: `url(${dsuBg})`,
      }}
    >
      {/* Overlay for readability */}
      <div className="absolute inset-0 bg-black bg-opacity-40"></div>

      <div className="relative z-10 bg-white/90 shadow-2xl rounded-2xl p-10 w-[25rem] text-center backdrop-blur-md border border-gray-300">
        {/* 🏫 DSU Logo */}
        <img
          src={dsuLogo}
          alt="DSU Logo"
          className="w-20 h-20 mx-auto mb-4 object-contain"
        />

        <h2 className="text-3xl font-semibold mb-6 text-gray-800 tracking-wide">
          DSU Portal Login
        </h2>

        {error && (
          <p className="text-red-500 mb-3 text-center font-medium">{error}</p>
        )}

        <form onSubmit={handleLogin} className="text-left">
          {/* Username */}
          <div className="mb-4">
            <input
              className="w-full border border-gray-300 focus:border-blue-600 rounded-lg p-2.5 outline-none transition"
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          {/* Password */}
          <div className="mb-4">
            <input
              className="w-full border border-gray-300 focus:border-blue-600 rounded-lg p-2.5 outline-none transition"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {/* Dummy Remember Me */}
          <div className="flex items-center mb-5">
            <input
              id="remember"
              type="checkbox"
              checked={remember}
              onChange={() => setRemember(!remember)}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded cursor-pointer"
            />
            <label htmlFor="remember" className="ml-2 text-sm text-gray-700">
              Remember me
            </label>
          </div>

          {/* Login Button */}
          <button
            className="w-full bg-blue-700 text-white py-2.5 rounded-lg font-medium hover:bg-blue-800 transition duration-200 shadow-md"
            type="submit"
          >
            Login
          </button>
        </form>

        <p className="text-xs text-gray-600 text-center mt-5">
          © {new Date().getFullYear()} Dayananda Sagar University
        </p>
      </div>
    </div>
  );
};

export default Login;
