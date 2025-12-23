import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import BriefingDetail from './pages/BriefingDetail'
import Topics from './pages/Topics'
import CreateTopic from './pages/CreateTopic'
import Casts from './pages/Casts'
import CreateCast from './pages/CreateCast'
import ManagePersonalities from './pages/ManagePersonalities'
import Settings from './pages/Settings'
import About from './pages/About'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="briefing/:id" element={<BriefingDetail />} />
        <Route path="topics" element={<Topics />} />
        <Route path="topics/create" element={<CreateTopic />} />
        <Route path="casts" element={<Casts />} />
        <Route path="casts/create" element={<CreateCast />} />
        <Route path="casts/personalities" element={<ManagePersonalities />} />
        <Route path="settings" element={<Settings />} />
        <Route path="about" element={<About />} />
      </Route>
    </Routes>
  )
}

export default App

