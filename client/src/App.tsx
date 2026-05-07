import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import CareerAdvisor from './pages/CareerAdvisor';


export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <nav className="navbar">
          <NavLink to="/" className="navbar-brand">
            SO<span>/</span>Expert<span>·</span>System
          </NavLink>
          <div className="navbar-links">
            <NavLink to="/"         end className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>Dashboard</NavLink>
            <NavLink to="/advisor"     className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>Career Advisor</NavLink>
          </div>
        </nav>

        <main className="main-content">
          <Routes>
            <Route path="/"         element={<Dashboard />} />
            <Route path="/advisor"  element={<CareerAdvisor />} />
          </Routes>
        </main>

        <footer>
          <p>Data: Stack Overflow Developer Survey 2024 · 90,184 Respondents</p>
          <p style={{ marginTop: '6px', opacity: 0.5 }}>Eissa Was Here</p>
        </footer>
      </div>
    </BrowserRouter>
  );
}
