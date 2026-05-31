import React, { useState, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import dsuLogo from "../assets/dsu_logo.png";
import dsuBg from "../assets/dsu.png";

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

      <div className="relative z-10 bg-white/95 shadow-2xl rounded-2xl p-10 w-[26rem] text-center backdrop-blur-sm border border-gray-200">
        <img
          src={dsuLogo}
          alt="DSU Logo"
          className="w-20 h-20 mx-auto mb-5 object-contain"
        />

        <h2 className="text-3xl font-semibold mb-2 text-gray-900">
          DSU Portal
        </h2>
        <p className="text-gray-600 mb-6 text-sm">
          Sign in to continue
        </p>

        {error && (
          <div className="alert-error mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="text-left">
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Username
            </label>
            <input
              className="input-field w-full"
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <input
              className="input-field w-full"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="flex items-center mb-6">
            <input
              id="remember"
              type="checkbox"
              checked={remember}
              onChange={() => setRemember(!remember)}
              className="h-4 w-4 text-indigo-600 border-gray-300 rounded cursor-pointer focus:ring-2 focus:ring-indigo-200"
            />
            <label htmlFor="remember" className="ml-2 text-sm text-gray-700">
              Remember me
            </label>
          </div>

          <button
            className="btn-primary w-full py-3"
            type="submit"
          >
            Sign In
          </button>
        </form>

        <p className="text-xs text-gray-500 text-center mt-6">
          © {new Date().getFullYear()} Dayananda Sagar University
        </p>
      </div>
    </div>
  );
};

export default Login;
