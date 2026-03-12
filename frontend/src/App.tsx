import { useState, useEffect } from 'react'
import { RotateCcw, List } from 'lucide-react'
import RepositorySetup from './components/RepositorySetup'
import MigrationProjectList from './components/MigrationProjectList'
import './App.css'

type Page = 'setup' | 'projects'

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('setup')

  return (
    <div className="app">
      <nav className="nav-bar">
        <div className="nav-container">
          <h1 className="nav-title">🚀 Framework Migration Tool</h1>
          <div className="nav-buttons">
            <button
              className={`nav-btn ${currentPage === 'setup' ? 'active' : ''}`}
              onClick={() => setCurrentPage('setup')}
            >
              <RotateCcw size={18} />
              New Migration
            </button>
            <button
              className={`nav-btn ${currentPage === 'projects' ? 'active' : ''}`}
              onClick={() => setCurrentPage('projects')}
            >
              <List size={18} />
              All Projects
            </button>
          </div>
        </div>
      </nav>

      <main className="main-content">
        {currentPage === 'setup' && <RepositorySetup />}
        {currentPage === 'projects' && <MigrationProjectList />}
      </main>
    </div>
  )
}

export default App

