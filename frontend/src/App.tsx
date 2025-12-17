import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import BriefingDetail from './pages/BriefingDetail'
import DeepCasts from './pages/DeepCasts'
import Stations from './pages/Stations'
import Topics from './pages/Topics'
import CustomSites from './pages/CustomSites'
import Settings from './pages/Settings'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="briefing/:id" element={<BriefingDetail />} />
        <Route path="deepcasts" element={<DeepCasts />} />
        <Route path="stations" element={<Stations />} />
        <Route path="topics" element={<Topics />} />
        <Route path="custom-sites" element={<CustomSites />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App

